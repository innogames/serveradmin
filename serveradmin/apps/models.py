from __future__ import division

import hashlib
from datetime import datetime

from django.db import models
from django.db.models.signals import pre_save
from django.contrib.auth.models import User

from serveradmin.common.utils import random_alnum_string

class Application(models.Model):
    name = models.CharField(max_length=80)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    author = models.ForeignKey(User)
    location = models.CharField(max_length=150)
    restricted = models.BooleanField(default=False)
    readonly = models.BooleanField(default=False)
    allowed_methods = models.TextField(blank=True)

    def __unicode__(self):
        return self.name

    def restriction_active(self):
        if not self.restricted:
            return False

        now = datetime.today()

        # Full friday to sunday
        if now.weekday() in (4, 5, 6):
            return True

        # Every day after 16:00
        if now.hour >= 16:
            return True

        return False

class ApplicationException(models.Model):
    application = models.ForeignKey(Application)
    user = models.ForeignKey(User)
    issue = models.TextField()
    changes = models.TextField()
    tested = models.BooleanField(default=False)
    granted = models.BooleanField(default=False)

    def __unicode__(self):
        return u'Exception on {0}'.format(self.application)

def set_auth_token(sender, instance, **kwargs):
    if not instance.auth_token:
        instance.auth_token = random_alnum_string(24)
    instance.app_id = hashlib.sha1(instance.auth_token).hexdigest()

pre_save.connect(set_auth_token, sender=Application)
