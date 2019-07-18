from __future__ import division
from base64 import b64encode, b64decode
from hashlib import sha256

from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from paramiko.ssh_exception import SSHException
from paramiko import RSAKey, ECDSAKey
try:
    from paramiko import Ed25519Key
except ImportError:
    # Ed25519Key requires paramiko >= 2.2
    pass

try:
    from paramiko import PublicBlob
except ImportError:
    # PublicBlob requires paramiko >= 2.3
    pass


from adminapi.request import calc_app_id
from serveradmin.common.utils import random_alnum_string


class Application(models.Model):
    name = models.CharField(max_length=80, unique=True)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    location = models.CharField(max_length=150)
    disabled = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, default=None, editable=False)
    superuser = models.BooleanField(default=False)
    allowed_methods = models.TextField(blank=True)

    def __str__(self):
        return self.name


@receiver(pre_save, sender=Application)
def set_auth_token(sender, instance, **kwargs):
    if not instance.auth_token:
        instance.auth_token = random_alnum_string(24)
    instance.app_id = calc_app_id(instance.auth_token)


@receiver(post_save, sender=User)
def set_disabled(sender, instance, **kwargs):
    """Set the applications to disabled when the owner is

    If the user is disabled, we are setting all of their applications
    to disabled as well, so that if they are enabled again,
    the applications wouldn't be automatically re-enabled.  Somebody
    doing this explicitly is a better idea.  The code should still check
    both application and the owner user being active to be on the safer
    side.  There are ways to change objects on Django without emitting
    signals like we are doing in here, and somebody can always change
    things on the database.
    """
    if not instance.is_active:
        Application.objects.filter(owner=instance).update(disabled=True)


class PublicKey(models.Model):
    application = models.ForeignKey(
        Application, related_name="public_keys", on_delete=models.CASCADE
    )
    key_algorithm = models.CharField(max_length=80)
    key_base64 = models.CharField(primary_key=True, max_length=2048)
    key_comment = models.CharField(max_length=80, blank=True)

    def __str__(self):
        if not (self.key_algorithm and self.key_base64):
            return self.key_comment
        # This format is used by ssh-add -l
        blob = self.load().asbytes()
        return 'SHA256:' + b64encode(sha256(blob).digest()).decode()

    def save(self, *args, **kwargs):
        """Call full_clean before save to ensure the key is loadable"""
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        """Load the key and raise ValidationError if it's not possible"""
        try:
            self.load()
        except SSHException as error:
            raise ValidationError('Loading public key failed: ' + str(error))

    def load(self):
        """Try to load the public key

        We support RSA, ECDSA and Ed25519 keys and return instances of:
        * paramiko.rsakey.RSAKey
        * paramiko.ecdsakey.ECDSAKey
        * paramiko.ed25519key.Ed25519Key (requires paramiko >= 2.2)
        """
        # I don't think there is a key type independent way of doing this
        public_key_blob = b64decode(self.key_base64)
        if self.key_algorithm.startswith('ssh-ed25519'):
            try:
                return Ed25519Key(data=public_key_blob)
            except NameError:
                raise ValidationError('Paramiko too old to load ed25519 keys')
        elif self.key_algorithm.startswith('ecdsa-'):
            return ECDSAKey(data=public_key_blob)
        elif self.key_algorithm.startswith('ssh-rsa'):
            return RSAKey(data=public_key_blob)

        raise SSHException('Key is not RSA, ECDSA or Ed25519')

    @classmethod
    def create(cls, application, public_key):
        """Convenience method to create a PublicKey from the string form"""
        try:
            loaded_public_key = PublicBlob.from_string(public_key)
            instance = cls(
                application=application,
                key_algorithm=loaded_public_key.key_type,
                key_base64=b64encode(loaded_public_key.key_blob).decode(),
                key_comment=loaded_public_key.comment,
            )
        except SSHException:
            raise ValidationError('Loading public key failed')
        except NameError:
            # XXX: Sketchy fallback for paramiko versions older than 2.3.
            # Remove this once we are on debian buster.
            public_key_parts = public_key.split()
            instance = cls(
                application=application,
                key_algorithm=public_key_parts[0],
                key_base64=public_key_parts[1],
                key_comment=(
                    public_key_parts[2] if len(public_key_parts) == 3 else ''
                ),
            )

        return instance
