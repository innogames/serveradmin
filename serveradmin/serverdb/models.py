import re
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


#
# Lookup Models
#
# We need a few models for extensibility of the system.  Those tables
# are going to store just a few rows, but we need those rows over and
# over again.  Django is not terribly good at optimising this.  It
# makes database queries every time a foreign key field is accessed.
# Using select_related() or prefetch_related() would mitigate this
# problem, but they would also cause the same rows to be downloaded
# over and over again.  What we really need it to read all of them
# just once.
#
# The existing caching solutions for Django are quite complicated for
# our need.  Here we are implementing a really basic Django Model
# Manager to read all rows for a model on first time one of them is
# accessed.
#
# We are, on purpose, not trying to override all functions of
# the manager.  Overriding the all() and get() methods are good enough
# for the callers on our application.  We don't want Django internals
# to use the cached objects anyway.
#
# We also need to encapsulate all the foreign keys to the lookup models
# for them to be cached.  Otherwise Django does some hard-to-interfere
# complicated magic on them.
#

attribute_types = (
    'integer',
    'string',
    'ip',
    'ipv6',
    'boolean',
    'datetime',
    'mac',
    'hostname',
    'number',
)


class LookupManager(models.Manager):
    """Custom Django model manager to cache lookup tables

    The purpose of this manager is to avoid accessing the lookup tables
    multiple times.
    """
    def __init__(self):
        super(LookupManager, self).__init__()
        self.reset_cache()

    def reset_cache(self):
        self._lookup_dict = None

    def all(self):
        """Override all method to cache all objects"""
        if not self._lookup_dict:
            self._lookup_dict = {
                o.pk: o for o in super(LookupManager, self).all()
            }
        return self._lookup_dict.values()

    def get(self, *args, **kwargs):
        """Override the get method to cache PK lookups

        We are only caching lookups with the special "pk" property.
        """
        if len(kwargs) == 1 and kwargs.keys()[0] == 'pk':
            value = kwargs.values()[0]

            # Initialise the cache
            self.all()

            # We are not relying the cache for misses.
            if value in self._lookup_dict:
                return self._lookup_dict[value]
            else:
                self.reset_cache()

        return super(LookupManager, self).get(*args, **kwargs)

    def create(self, *args, **kwargs):
        self.reset_cache()
        return super(LookupManager, self).create(*args, **kwargs)


class LookupModel(models.Model):
    _default_manager = models.Manager()
    objects = LookupManager()

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.pk

    def save(self, *args, **kwargs):
        type(self).objects.reset_cache()
        return super(LookupModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        type(self).objects.reset_cache()
        return super(LookupModel, self).delete(*args, **kwargs)

    @classmethod
    def foreign_key_lookup(cls, field):

        @property
        def wrapped(self):
            """Encapsulate the foreign key field"""
            if getattr(self, field):
                model = type(self) if cls == LookupModel else cls
                return model.objects.get(pk=getattr(self, field))

        return wrapped


class Project(LookupModel):
    project_id = models.CharField(max_length=32, primary_key=True)
    subdomain = models.CharField(max_length=16, unique=True)
    responsible_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'project'
        ordering = ('pk', )


class Segment(LookupModel):
    segment_id = models.CharField(max_length=20, primary_key=True)
    ip_range = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'segment'
        ordering = ('pk', )


class Servertype(LookupModel):
    servertype_id = models.CharField(max_length=32, primary_key=True)
    description = models.CharField(max_length=1024)
    _fixed_project = models.ForeignKey(
        Project,
        blank=True,
        null=True,
        db_column='fixed_project_id',
        on_delete=models.PROTECT,
    )
    fixed_project = Project.foreign_key_lookup('_fixed_project_id')

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'
        ordering = ('pk', )

    def copy(self, new_id):
        target, created = Servertype.objects.get_or_create(pk=new_id)
        skip = [a.attribute for a in target.used_attributes.select_related()]

        for servertype_attribute in self.used_attributes.select_related():
            if servertype_attribute.attribute in skip:
                continue

            ServertypeAttribute.objects.create(
                _servertype=target,
                _attribute=servertype_attribute.attribute,
                required=servertype_attribute.required,
                default_value=servertype_attribute.default_value,
                regexp=servertype_attribute.regexp,
                default_visible=servertype_attribute.default_visible,
            )

            clear_lookups()


class Attribute(LookupModel):
    special = None

    def __init__(self, *args, **kwargs):
        if 'special' in kwargs:
            self.special = kwargs[u'special']
            del kwargs[u'special']
        super(Attribute, self).__init__(*args, **kwargs)

    attribute_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_column='attrib_id',
    )
    type = models.CharField(
        max_length=32,

        # Django allows the choices to be stored and named differently,
        # but we don't need it.  We are zipping the tuple to itself
        # to use the same names.
        choices=zip(*((attribute_types, ) * 2)),
    )
    base = models.BooleanField(default=False)
    multi = models.BooleanField(default=False)
    hovertext = models.TextField(blank=True, default='')
    group = models.CharField(max_length=32, default='other')
    help_link = models.CharField(max_length=255, blank=True, null=True)
    readonly = models.BooleanField(default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib'
        ordering = ('pk', )

    def used_in(self):
        return [
            sa.servertype
            for sa in ServertypeAttribute.objects.all()
            if sa.attribute == self
        ]

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


class ServertypeAttribute(LookupModel):
    _servertype = models.ForeignKey(
        Servertype,
        related_name='used_attributes',
        db_column='servertype_id',
        db_index=False,
        on_delete=models.CASCADE,
    )
    servertype = Servertype.foreign_key_lookup('_servertype_id')
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attrib_id',
        db_index=False,
        on_delete=models.CASCADE,
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    required = models.BooleanField(default=False)
    default_value = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='attrib_default',
    )
    regexp = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='regex',
    )
    _compiled_regexp = None
    default_visible = models.BooleanField(default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype_attributes'
        unique_together = (('_servertype', '_attribute'), )

    def __unicode__(self):
        return '{0} - {1}'.format(self.servertype, self.attribute)

    def get_compiled_regexp(self):
        if self.regexp and not self._compiled_regexp:
            self._compiled_regexp = re.compile(self.regexp)
        return self._compiled_regexp

    def regexp_match(self, value):
        if self.regexp:
            return self.get_compiled_regexp().match(str(value))


#
# Server Models
#
# Servers are the main objects of the system.  They are stored in
# entity-attribute-value schema.
#

class Server(models.Model):
    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(max_length=64, unique=True)
    intern_ip = dbfields.IPv4Field(db_index=True)
    comment = models.CharField(max_length=255, null=True, blank=True)
    _project = models.ForeignKey(
        Project,
        db_column='project_id',
        on_delete=models.PROTECT,
    )
    project = Project.foreign_key_lookup('_project_id')
    _segment = models.ForeignKey(
        Segment,
        db_column='segment_id',
        on_delete=models.PROTECT,
    )
    segment = Segment.foreign_key_lookup('_segment_id')
    _servertype = models.ForeignKey(
        Servertype,
        db_column='servertype_id',
        on_delete=models.PROTECT,
    )
    servertype = Servertype.foreign_key_lookup('_servertype_id')

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

        return queryset.filter(_attribute=attribute)

    def add_attribute(self, attribute, value):
        if attribute.type == 'hostname':
            server_attribute = ServerHostnameAttribute(
                _attribute=attribute,
                value=Server.objects.get(hostname=value),
            )
            self.serverhostnameattribute_set.add(server_attribute)
        else:
            server_attribute = ServerStringAttribute(
                _attribute=attribute,
                value=attribute.serialize_value(value),
            )
            self.serverstringattribute_set.add(server_attribute)

        return server_attribute


class ServerAttribute(models.Model):
    server = models.ForeignKey(
        Server,
        db_index=False,
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def __unicode__(self):
        return '{0}->{1}={2}'.format(self.server, self.attribute, self.value)

    def reset(self, value):
        self.value = value

    def matches(self, value):
        return self.value in value


class ServerHostnameAttributeManager(models.Manager):
    def get_queryset(self):
        manager = super(ServerHostnameAttributeManager, self)
        return manager.get_queryset().select_related('value')


class ServerHostnameAttribute(ServerAttribute):
    objects = ServerHostnameAttributeManager()

    _attribute = models.ForeignKey(
        Attribute,
        db_column='attrib_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to={'type': 'hostname'},
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = models.ForeignKey(
        Server,
        db_column='value',
        db_index=False,
        on_delete=models.PROTECT,
        related_name='hostname_attribute_servers',
        related_query_name='hostname_attribute_server',
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_hostname_attrib'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )

    def reset(self, value):
        self.value = Server.objects.get(hostname=value)

    def matches(self, values):
        return self.value in (
            Server.objects.get(hostname=v) for v in values
        )


class ServerStringAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attrib_id',
        db_index=False,
        on_delete=models.CASCADE,
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'attrib_values'

    def reset(self, value):
        self.value = self.attribute.serialize_value(value)

    def matches(self, values):
        return self.value in (
            self.attribute.serialize_value(v) for v in values
        )


#
# Change Log Models
#

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
