import json
import time

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

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
    ('mac', 'MAC address'),
    ('hostname', 'Hostname'),
)


class Project(models.Model):
    project_id = models.CharField(max_length=32, primary_key=True)
    subdomain = models.CharField(max_length=16, unique=True)
    responsible_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'project'
        ordering = ('project_id', )

    def __unicode__(self):
        return self.project_id


class ServerType(models.Model):
    servertype_id = models.CharField(max_length=32, primary_key=True)
    description = models.CharField(max_length=1024)
    fixed_project = models.ForeignKey(
        Project,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
    )

    def copy(self, new_id):
        target, created = ServerType.objects.get_or_create(pk=new_id)
        skip = [a.attrib for a in target.used_attributes.select_related()]

        for servertype_attribute in self.used_attributes.select_related():
            if servertype_attribute.attrib in skip:
                continue

            ServerTypeAttribute.objects.create(
                servertype=target,
                attrib=servertype_attribute.attrib,
                required=servertype_attribute.required,
                attrib_default=servertype_attribute.attrib_default,
                regex=servertype_attribute.regex,
                default_visible=servertype_attribute.default_visible,
            )

            clear_lookups()

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'
        ordering = ('servertype_id', )

    def __unicode__(self):
        return self.servertype_id


class Attribute(models.Model):
    special = None

    def __init__(self, *args, **kwargs):
        if 'special' in kwargs:
            self.special = kwargs[u'special']
            del kwargs[u'special']
        super(Attribute, self).__init__(*args, **kwargs)

    attrib_id = models.CharField(max_length=32, primary_key=True)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    base = models.BooleanField(default=False)
    multi = models.BooleanField(default=False)
    hovertext = models.TextField(blank=True, default='')
    group = models.CharField(max_length=32, default='other')
    help_link = models.CharField(max_length=255, blank=True, null=True)
    readonly = models.BooleanField(default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib'
        ordering = ('attrib_id', )

    def __unicode__(self):
        return self.attrib_id

    def used_in(self):
        queryset = ServerTypeAttribute.objects.select_related('servertype')
        queryset = queryset.filter(attrib=self).order_by('servertype')
        return [x.servertype for x in queryset]

    def external_link(self):
        if self.help_link:
            return self.help_link
        return self.search_link()

    def search_link(self):
        return settings.ATTRIBUTE_WIKI_LINK.format(attr=self.pk)

    def serialize_value(self, value):

        if self.type == u'boolean':
            value = 1 if value else 0

        if self.type == u'ip':
            if not isinstance(value, IPv4Address):
                value = IPv4Address(value)
            value = int(value)

        if self.type == u'ipv6':
            if not isinstance(value, IPv6Address):
                value = IPv6Address(value)
            value = ''.join('{:02x}'.format(x) for x in value.packed)

        if self.type == u'datetime':
            if isinstance(value, datetime):
                value = int(time.mktime(value.timetuple()))

        return str(value)


class ServerTypeAttribute(models.Model):
    servertype = models.ForeignKey(
        ServerType,
        related_name='used_attributes',
        db_index=False,
        on_delete=models.CASCADE,
    )
    attrib = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
    )
    required = models.BooleanField(default=False)
    attrib_default = models.CharField(max_length=255, null=True, blank=True)
    regex = models.CharField(max_length=255, null=True, blank=True)
    default_visible = models.BooleanField(default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype_attributes'
        unique_together = (('servertype', 'attrib'), )


class Segment(models.Model):
    segment_id = models.CharField(max_length=20, primary_key=True)
    ip_range = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'segment'
        ordering = ('segment_id', )

    def __unicode__(self):
        return self.segment_id


class ServerObject(models.Model):
    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(max_length=64, unique=True)
    intern_ip = dbfields.IPv4Field(db_index=True)
    comment = models.CharField(max_length=255, null=True, blank=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
    )
    servertype = models.ForeignKey(
        ServerType,
        on_delete=models.PROTECT,
    )
    segment = models.ForeignKey(
        Segment,
        on_delete=models.PROTECT,
    )

    def __str__(self):
        return self.hostname

    class Meta:
        app_label = 'serverdb'
        db_table = 'admin_server'

    def get_attributes(self, attribute):

        if attribute.type == 'hostname':
            queryset = self.serverhostnameattribute_set
        else:
            queryset = self.serverstringattribute_set

        return queryset.filter(attrib=attribute)

    def add_attribute(self, attribute, value):

        if attribute.type == 'hostname':
            server_attribute = ServerHostnameAttribute(
                attrib=attribute,
                value=ServerObject.objects.get(hostname=value),
            )
            self.serverhostnameattribute_set.add(server_attribute)

        else:
            server_attribute = ServerStringAttribute(
                attrib=attribute,
                value=attribute.serialize_value(value),
            )
            self.serverstringattribute_set.add(server_attribute)

        return server_attribute


class ServerAttribute(models.Model):
    server = models.ForeignKey(
        ServerObject,
        db_index=False,
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def __unicode__(self):
        return '{0}->{1}={2}'.format(self.server, self.attrib, self.value)

    def reset(self, value):
        self.value = value

    def matches(self, value):
        return self.value in value


class ServerHostnameAttribute(ServerAttribute):
    attrib = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to={'type': 'hostname'},
    )
    value = models.ForeignKey(
        ServerObject,
        db_column='value',
        db_index=False,
        on_delete=models.PROTECT,
        related_name='hostname_attribute_servers',
        related_query_name='hostname_attribute_server',
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_hostname_attrib'
        unique_together = (('server', 'attrib', 'value'), )
        index_together = (('attrib', 'value'), )

    def reset(self, value):
        self.value = ServerObject.objects.get(hostname=value)

    def matches(self, values):
        return self.value in (
            ServerObject.objects.get(hostname=v) for v in values
        )


class ServerStringAttribute(ServerAttribute):
    attrib = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
    )
    value = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib_values'

    def reset(self, value):
        self.value = self.attrib.serialize_value(value)

    def matches(self, values):
        return self.value in (self.attrib.serialize_value(v) for v in values)


class Change(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.PROTECT,
    )
    app = models.ForeignKey(
        Application,
        null=True,
        on_delete=models.PROTECT,
    )
    changes_json = models.TextField()

    class Meta:
        app_label = 'serverdb'

    @property
    def changes(self):
        return json.loads(self.changes_json)

    def __unicode__(self):
        return unicode(self.change_on)


class ChangeCommit(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.PROTECT,
    )
    app = models.ForeignKey(
        Application,
        null=True,
        on_delete=models.PROTECT,
    )

    class Meta:
        app_label = 'serverdb'

    def __unicode__(self):
        return unicode(self.change_on)


class ChangeDelete(models.Model):
    commit = models.ForeignKey(
        ChangeCommit,
        on_delete=models.CASCADE,
    )
    hostname = models.CharField(max_length=64, db_index=True)
    attributes_json = models.TextField()

    class Meta:
        app_label = 'serverdb'

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)


class ChangeUpdate(models.Model):
    commit = models.ForeignKey(
        ChangeCommit,
        on_delete=models.CASCADE,
    )
    hostname = models.CharField(max_length=64, db_index=True)
    updates_json = models.TextField()

    class Meta:
        app_label = 'serverdb'

    @property
    def updates(self):
        return json.loads(self.updates_json)

    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)


class ChangeAdd(models.Model):
    commit = models.ForeignKey(
        ChangeCommit,
        on_delete=models.CASCADE,
    )
    hostname = models.CharField(max_length=64, db_index=True)
    attributes_json = models.TextField()

    class Meta:
        app_label = 'serverdb'

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __unicode__(self):
        return u'{0}: {1}'.format(unicode(self.commit), self.hostname)


def clear_lookups(*args, **kwargs):
    cache.delete('dataset_lookups_version')

post_save.connect(clear_lookups, sender=Attribute)
