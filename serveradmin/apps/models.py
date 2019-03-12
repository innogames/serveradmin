from __future__ import division

from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from adminapi.request import calc_app_id
from serveradmin.common.utils import random_alnum_string


class Application(models.Model):
    name = models.CharField(max_length=80, unique=True)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    location = models.CharField(max_length=150)
    disabled = models.BooleanField(default=False)
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
