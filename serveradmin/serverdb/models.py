import json

from django.db import models
from django.db.models.signals import post_save
from django.core.cache import cache
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.conf import settings

from serveradmin.common import dbfields
from serveradmin.apps.models import Application

TYPE_CHOICES = (
        ('integer', 'Integer'),
        ('string', 'String'),
        ('ip', 'IPv4 address'),
        ('ipv6', 'IPv6 address'),
        ('boolean', 'Boolean'),
        ('datetime', 'Datetime'),
        ('mac', 'MAC address')
)

class Attribute(models.Model):
    special = None
    def __init__(self, *args, **kwargs):
        if 'special' in kwargs:
            self.special = kwargs[u'special']
            del kwargs[u'special']
        super(Attribute, self).__init__(*args, **kwargs)

    attrib_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64)
    type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    base = models.BooleanField(default=False)
    multi = models.BooleanField(default=False)
    hovertext = models.TextField(blank=True, default='')
    group = models.CharField(max_length=64, default='other')

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib'
        ordering = ('name', )

    def __unicode__(self):
        return self.name

    def used_in(self):
        stype_attrs = (ServerTypeAttributes.objects.select_related('servertype')
                      .filter(attrib=self).order_by('servertype__name'))
        return [x.servertype for x in stype_attrs]

    def wiki_link(self):
        return settings.ATTRIBUTE_WIKI_LINK.format(attr=self.name)

class ServerType(models.Model):
    servertype_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)

    def copy(self, new_name):
        target, created = ServerType.objects.get_or_create(name=new_name)
        skip = set([attr.attrib.name for attr in
                target.used_attributes.select_related()])

        for attr in self.used_attributes.select_related():
            if attr.attrib.name in skip:
                continue
            ServerTypeAttributes.objects.create(
                    servertype=target,
                    attrib=attr.attrib,
                    required=attr.required,
                    attrib_default=attr.attrib_default,
                    regex=attr.regex,
                    default_visible=attr.default_visible)
            clear_lookups()


    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'

    def __unicode__(self):
        return self.name

class ServerTypeAttributes(models.Model):
    servertype = models.ForeignKey(ServerType, related_name='used_attributes')
    attrib = models.ForeignKey(Attribute)
    required = models.BooleanField(default=False)
    attrib_default = models.CharField(max_length=255, null=True, blank=True)
    regex = models.CharField(max_length=255, null=True, blank=True)
    default_visible = models.BooleanField(default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype_attributes'
        unique_together = (('servertype', 'attrib'), )

class ServerObject(models.Model):
    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(max_length=64)
    intern_ip = dbfields.IPv4Field()
    comment = models.CharField(max_length=255, null=True, blank=True)
    servertype = models.ForeignKey(ServerType, null=True, blank=True)
    segment = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        app_label = 'serverdb'
        db_table = 'admin_server'

class AttributeValue(models.Model):
    server = models.ForeignKey(ServerObject)
    attrib = models.ForeignKey(Attribute)
    value = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib_values'

class ServerObjectCache(models.Model):
    server = models.ForeignKey(ServerObject, null=True, blank=True)
    repr_hash = models.BigIntegerField()

    class Meta:
        app_label = 'serverdb'
        unique_together = (('server', 'repr_hash'))

class Segment(models.Model):
    segment = models.CharField(max_length=20, db_column='segment_id',
            primary_key=True)

    class Meta:
        app_label = 'serverdb'
        db_table = 'segment'

class SegmentUsage(models.Model):
    segment = models.OneToOneField(Segment, related_name='usage')
    description = models.TextField()

    def __unicode__(self):
        return '{0}: {1}'.format(self.segment, self.description)

    class Meta:
        app_label = 'serverdb'


class Change(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True)
    app = models.ForeignKey(Application, blank=True, null=True)
    changes_json = models.TextField()

    @property
    def changes(self):
        return json.loads(self.changes_json)

    def __unicode__(self):
        return unicode(self.change_on)

    class Meta:
        app_label = 'serverdb'


class ChangeCommit(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(User, blank=True, null=True)
    app = models.ForeignKey(Application, blank=True, null=True)
    
    def __unicode__(self):
        return unicode(self.change_on)

    class Meta:
        app_label = 'serverdb'


class ChangeDelete(models.Model):
    commit = models.ForeignKey(ChangeCommit)
    hostname = models.CharField(max_length=64, db_index=True)
    attributes_json = models.TextField()

    @property
    def attributes(self):
        return json.loads(self.attributes_json)
    
    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)

    class Meta:
        app_label = 'serverdb'


class ChangeUpdate(models.Model):
    commit = models.ForeignKey(ChangeCommit)
    hostname = models.CharField(max_length=64, db_index=True)
    updates_json = models.TextField()

    @property
    def updates(self):
        return json.loads(self.updates_json)

    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)

    class Meta:
        app_label = 'serverdb'


class ChangeAdd(models.Model):
    commit = models.ForeignKey(ChangeCommit)
    hostname = models.CharField(max_length=64, db_index=True)
    attributes_json = models.TextField()

    @property
    def attributes(self):
        return json.loads(self.attributes_json)
    
    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)

    class Meta:
        app_label = 'serverdb'


def clear_lookups():
    cache.delete('dataset_lookups_version')


def _attribute_changed(sender, **kwargs):
    clear_lookups()
post_save.connect(_attribute_changed, sender=Attribute)
