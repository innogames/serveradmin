from __future__ import division
import random
import string
import hashlib
from datetime import datetime

from django.db import models
from django.db.models.signals import pre_save, pre_delete, post_save
from django.contrib.auth.models import User

class Application(models.Model):
    name = models.CharField(max_length=80)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    author = models.ForeignKey(User)
    location = models.CharField(max_length=150)
    restricted = models.BooleanField(default=False)

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

class ApplicationStatistic(models.Model):
    application = models.OneToOneField(Application)
    num_queries = models.PositiveIntegerField(default=0)
    query_time = models.PositiveIntegerField(default=0) # msec
    num_api_calls = models.PositiveIntegerField(default=0)
    api_call_time = models.PositiveIntegerField(default=0) # msec

    @property
    def avg_query_time(self):
        return self.query_time / self.num_queries

    @property
    def avg_api_call_time(self):
        return self.api_call_time / self.num_api_calls

def _app_changed(sender, instance, **kwargs):
    if not instance.auth_token:
        token_chars = string.letters + string.digits
        token = ''.join(random.choice(token_chars) for _i in xrange(24))
        instance.auth_token = token
    instance.app_id = hashlib.sha1(instance.auth_token).hexdigest()

def _app_created(sender, instance, created, **kwargs):
    if created:
        ApplicationStatistic.objects.create(application=instance)

def _app_deleted(sender, instance, **kwargs):
    ApplicationStatistic.objects.get(application=instance).delete()

pre_save.connect(_app_changed, sender=Application)
post_save.connect(_app_created, sender=Application)
pre_delete.connect(_app_deleted, sender=Application)
