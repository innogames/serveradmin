from __future__ import division

from django.db import models
from django.db.models.signals import pre_save
from django.contrib.auth.models import User

from adminapi.request import calc_app_id
from serveradmin.common.utils import random_alnum_string


class Application(models.Model):
    name = models.CharField(max_length=80, unique=True)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    owner = models.ForeignKey(User)
    location = models.CharField(max_length=150)
    disabled = models.BooleanField(default=False)
    superuser = models.BooleanField(default=False)
    allowed_methods = models.TextField(blank=True)

    def __str__(self):
        return self.name


def set_auth_token(sender, instance, **kwargs):
    if not instance.auth_token:
        instance.auth_token = random_alnum_string(24)
    instance.app_id = calc_app_id(instance.auth_token)


pre_save.connect(set_auth_token, sender=Application)
