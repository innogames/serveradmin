from __future__ import division
import random
import string
import hashlib

from django.db import models
from django.db.models.signals import pre_save, pre_delete, post_save
from django.contrib.auth.models import User

class Application(models.Model):
    name = models.CharField(max_length=80)
    app_id = models.CharField(max_length=64, unique=True, editable=False)
    auth_token = models.CharField(max_length=64, unique=True, editable=False)
    author = models.ForeignKey(User)
    location = models.CharField(max_length=150)

    def __unicode__(self):
        return self.name

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
        token = ''.join(random.choice(string.letters) for _i in xrange(16))
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
