import re
import json

from collections import OrderedDict
from ipaddress import ip_network
from itertools import chain

from django.db import models
from django.core.exceptions import ValidationError
from django.core.signals import request_started
from django.core.validators import RegexValidator
from django.utils.timezone import now
from django.contrib.auth.models import User

import netfields

from serveradmin.apps.models import Application


#
# Lookup Models
#
# We need a few models for extensibility of the system.  Those tables
# are going to store just a few rows, but we need those rows over and
# over again.  Django is not terribly good at optimizing this.  It
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
    'string',
    'boolean',
    'hostname',
    'reverse_hostname',
    'number',
    'inet',
    'macaddr',
    'date',
    'supernet',
)

ip_addr_types = (
    'null',
    'host',
    'loadbalancer',
    'network',
)

lookup_id_validators = [
    RegexValidator('^[a-z][a-z0-9_]*$', 'Invalid id'),
]

hostname_validators = [
    RegexValidator('^[a-z][a-z0-9\.\-]*$', 'Invalid hostname'),
]


def get_choices(types):
    # Django allows the choices to be stored and named differently,
    # but we don't need it.  We are zipping the tuple to itself
    # to use the same names.
    return zip(*((types, ) * 2))


class LookupManager(models.Manager):
    """Custom Django model manager to cache lookup tables

    The purpose of this manager is to avoid accessing the lookup tables
    multiple times.
    """
    def __init__(self):
        super(LookupManager, self).__init__()
        self._reset_cache()
        # Make sure the cache is clean on every new request.
        request_started.connect(self._reset_cache)

    def _reset_cache(self, **kwargs):
        self._cache_built = False
        self._lookup_dict = {}

    def _build_cache(self):
        self._cache_built = True
        self._lookup_dict = OrderedDict(
            (o.pk, o) for o in super(LookupManager, self).all()
        )

    def all(self):
        """Override all method to cache all objects"""
        if not self._cache_built:
            self._build_cache()
        return self._lookup_dict.values()

    def get(self, *args, **kwargs):
        """Override the get method to cache PK lookups

        We are only caching lookups with the special "pk" property.
        """
        # Implement anti-cache pattern to make things faster in here.
        # This is one of the hottest function of the application according
        # to the profiles.
        for key, value in kwargs.items():
            if key != 'pk':
                raise Exception(
                    'get() except "pk" are not supported on lookup models.'
                )
            if value not in self._lookup_dict:
                if not self._cache_built:
                    self._build_cache()
                    return self.get(*args, **kwargs)
                raise self.model.DoesNotExist(
                    'Attribute "{0}" does not exist.'.format(value)
                )
            return self._lookup_dict[value]

    def create(self, *args, **kwargs):
        super(LookupManager, self).create(*args, **kwargs)
        self._reset_cache()


class LookupModel(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.pk

    def save(self, *args, **kwargs):
        super(LookupModel, self).save(*args, **kwargs)
        type(self).objects._reset_cache()

    def delete(self, *args, **kwargs):
        super(LookupModel, self).delete(*args, **kwargs)
        type(self).objects._reset_cache()

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
    objects = LookupManager()

    project_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_index=False,
        validators=lookup_id_validators,
    )
    subdomain = models.CharField(
        max_length=16,
        unique=True,
        db_index=False,
        validators=hostname_validators,
    )
    responsible_admin = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_index=False,
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'project'
        ordering = ('pk', )


class Servertype(LookupModel):
    objects = LookupManager()

    servertype_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_index=False,
        validators=lookup_id_validators,
    )
    description = models.CharField(max_length=1024)
    _fixed_project = models.ForeignKey(
        Project,
        blank=True,
        null=True,
        db_column='fixed_project_id',
        db_index=False,
        on_delete=models.PROTECT,
    )
    fixed_project = Project.foreign_key_lookup('_fixed_project_id')
    ip_addr_type = models.CharField(
        max_length=32,
        choices=get_choices(ip_addr_types),
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'
        ordering = ('pk', )


class AttributeManager(LookupManager):
    def _build_cache(self):
        super(AttributeManager, self)._build_cache()
        self._lookup_dict = OrderedDict(chain(
            Attribute.specials.items(), self._lookup_dict.items()
        ))


class Attribute(LookupModel):
    objects = AttributeManager()
    special = None

    def __init__(self, *args, **kwargs):
        if 'special' in kwargs:
            self.special = kwargs['special']
            del kwargs['special']
        super(Attribute, self).__init__(*args, **kwargs)

    attribute_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_index=False,
        validators=lookup_id_validators,
    )
    type = models.CharField(
        max_length=32,
        choices=get_choices(attribute_types),
    )
    multi = models.BooleanField(null=False, default=False)
    hovertext = models.TextField(null=False, blank=True, default='')
    group = models.CharField(
        max_length=32, null=False, blank=False, default='other'
    )
    help_link = models.CharField(max_length=255, blank=True, null=True)
    readonly = models.BooleanField(null=False, default=False)
    _target_servertype = models.ForeignKey(
        Servertype,
        db_column='target_servertype_id',
        db_index=False,
        null=True,
        blank=True,
    )
    _reversed_attribute = models.ForeignKey(
        'self',
        related_name='reversed_attribute_set',
        null=True,
        blank=True,
        db_column='reversed_attribute_id',
        db_index=False,
        limit_choices_to=dict(type='hostname'),
    )
    reversed_attribute = LookupModel.foreign_key_lookup(
        '_reversed_attribute_id'
    )
    target_servertype = Servertype.foreign_key_lookup('_target_servertype_id')

    class Meta:
        app_label = 'serverdb'
        db_table = 'attribute'
        ordering = ('pk', )

    @property
    def related_servertype_attributes(self):
        return self.servertype_attributes.filter(
            _related_via_attribute__isnull=False
        )

    def can_be_materialized(self):
        return bool(ServerAttribute.get_model(self.type))

    def initializer(self):
        if self.multi:
            return set
        if self.type == 'boolean':
            return bool
        return lambda: None


class ServerTableSpecial(object):
    def __init__(self, field, unique=False):
        self.field = field
        self.unique = unique


Attribute.specials = {
    'object_id': Attribute(
        attribute_id='object_id',
        type='number',
        multi=False,
        group='base',
        special=ServerTableSpecial('server_id'),
    ),
    'hostname': Attribute(
        attribute_id='hostname',
        type='string',
        multi=False,
        group='base',
        special=ServerTableSpecial('hostname', unique=True),
    ),
    'servertype': Attribute(
        attribute_id='servertype',
        type='string',
        multi=False,
        group='base',
        special=ServerTableSpecial('_servertype_id'),
    ),
    'project': Attribute(
        attribute_id='project',
        type='string',
        multi=False,
        group='base',
        special=ServerTableSpecial('_project_id'),
    ),
    'intern_ip': Attribute(
        attribute_id='intern_ip',
        type='inet',
        multi=False,
        group='base',
        special=ServerTableSpecial('intern_ip'),
    ),
}


#
# Servertype Attribute Relation
#

class ServertypeAttribute(models.Model):
    _servertype = models.ForeignKey(
        Servertype,
        related_name='attributes',
        db_column='servertype_id',
        db_index=False,
        on_delete=models.CASCADE,
    )
    servertype = Servertype.foreign_key_lookup('_servertype_id')
    _attribute = models.ForeignKey(
        Attribute,
        related_name='servertype_attributes',
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    _related_via_attribute = models.ForeignKey(
        Attribute,
        related_name='related_via_servertype_attributes',
        null=True,
        blank=True,
        db_column='related_via_attribute_id',
        db_index=False,
        # It can only be related via a relation (AKA as an hostname
        # attribute).
        limit_choices_to=models.Q(type__in=(
            'hostname', 'reverse_hostname', 'supernet'
        )),
    )
    related_via_attribute = Attribute.foreign_key_lookup(
        '_related_via_attribute_id'
    )
    required = models.BooleanField(null=False, default=False)
    default_value = models.CharField(max_length=255, null=True, blank=True)
    regexp = models.CharField(max_length=255, null=True, blank=True)
    _compiled_regexp = None
    default_visible = models.BooleanField(null=False, default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype_attribute'
        unique_together = (('_servertype', '_attribute'), )

    def __str__(self):
        return '{0} - {1}'.format(self.servertype, self.attribute)

    def get_compiled_regexp(self):
        if self.regexp is not None and not self._compiled_regexp:
            self._compiled_regexp = re.compile(self.regexp)
        return self._compiled_regexp

    def get_default_value(self):
        if self.default_value and self.attribute.type == 'string':
            if self.attribute.multi:
                return {self.default_value}
            return self.default_value
        return self.attribute.initializer()()

    def regexp_match(self, value):
        return self.get_compiled_regexp().match(str(value))

    def clean(self):
        if self.default_value == '':
            self.default_value = None
        if self.regexp == '':
            self.regexp = None
        super(ServertypeAttribute, self).clean()

    @classmethod
    def query(self, servertypes=None, attributes=None):
        queryset = self.objects
        if servertypes is not None:
            queryset = queryset.filter(_servertype__in=servertypes)
        if attributes is not None:
            queryset = queryset.filter(_attribute__in=attributes)
        return queryset


#
# Server Models
#
# Servers are the main objects of the system.  They are stored in
# entity-attribute-value schema.  There are multiple models to store
# the attribute values of the servers by different data types.
#

class Server(models.Model):
    objects = netfields.NetManager()

    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(
        max_length=64,
        unique=True,
        validators=hostname_validators,
    )
    intern_ip = netfields.InetAddressField(null=True, blank=True)
    _project = models.ForeignKey(
        Project,
        db_column='project_id',
        on_delete=models.PROTECT,
    )
    project = Project.foreign_key_lookup('_project_id')
    _servertype = models.ForeignKey(
        Servertype,
        db_column='servertype_id',
        on_delete=models.PROTECT,
    )
    servertype = Servertype.foreign_key_lookup('_servertype_id')

    class Meta:
        app_label = 'serverdb'
        db_table = 'server'

    def __str__(self):
        return self.hostname

    def get_supernet(self, servertype):
        return Server.objects.get(
            _servertype=servertype,
            intern_ip__net_contains_or_equals=self.intern_ip,
        )

    def clean(self, *args, **kwargs):
        super(Server, self).clean(*args, **kwargs)
        self._validate_project()
        if self.servertype.ip_addr_type == 'null':
            self._validate_null_intern_ip()
        elif self.servertype.ip_addr_type in ('host', 'loadbalancer'):
            self._validate_host_intern_ip()
        elif self.servertype.ip_addr_type == 'network':
            self._validate_network_intern_ip()

    def _validate_project(self):
        fixed_project = self.servertype.fixed_project
        if fixed_project and self.project != fixed_project:
            raise ValidationError(
                'Project has to be "{0}".'.format(fixed_project)
            )

    def _validate_null_intern_ip(self):
        if self.intern_ip is not None:
            raise ValidationError('IP address must be null.')

    def _validate_host_intern_ip(self):
        if self.intern_ip.max_prefixlen != self.netmask_len():
            raise ValidationError(
                'Netmask length must be {0}.'
                .format(self.intern_ip.max_prefixlen)
            )

        # Check for other server with overlapping addresses
        for server in Server.objects.filter(
            intern_ip__net_overlaps=self.intern_ip
        ).exclude(pk=self.pk):
            if (
                server.servertype.ip_addr_type == 'network' and
                server.project != self.project and
                not server.servertype.fixed_project and
                not self.servertype.fixed_project
            ):
                raise ValidationError(
                    'IP address overlaps with the network "{0}" from '
                    'a different project.'
                    .format(server.hostname)
                )

            if server.servertype.ip_addr_type == 'host':
                raise ValidationError(
                    'IP address already taken by the host "{0}".'
                    .format(server.hostname)
                )

            if server.servertype.ip_addr_type == 'loadbalancer' and (
                server.servertype != self.servertype or
                server.project != self.project
            ):
                raise ValidationError(
                    'IP address already taken by the loadbalancer "{0}" from '
                    'a different project.'
                    .format(server.hostname)
                )

    def _validate_network_intern_ip(self):
        try:
            ip_network(str(self.intern_ip))
        except ValueError as error:
            raise ValidationError(str(error))

        # Check for other server with overlapping addresses
        for server in Server.objects.filter(
            intern_ip__net_overlaps=self.intern_ip
        ).exclude(pk=self.pk):
            if (
                server.project != self.project and
                not server.servertype.fixed_project and
                not self.servertype.fixed_project
            ):
                raise ValidationError(
                    'IP address overlaps with "{0}" from a different '
                    'project.'
                    .format(server.hostname)
                )

            if self.servertype == server.servertype:
                raise ValidationError(
                    'IP address overlaps with "{0}" in the same '
                    'servertype.'
                    .format(server.hostname)
                )

    def netmask_len(self):
        return self.intern_ip.network.prefixlen

    def get_attributes(self, attribute):
        model = ServerAttribute.get_model(attribute.type)
        return model.objects.filter(server=self, _attribute=attribute)

    def add_attribute(self, attribute, value):
        model = ServerAttribute.get_model(attribute.type)
        if model is ServerBooleanAttribute and not value:
            return
        server_attribute = model(server=self, _attribute=attribute)
        server_attribute.save_value(value)


class ServerAttribute(models.Model):
    server = models.ForeignKey(
        Server,
        db_index=False,
        on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return '{0}->{1}={2}'.format(self.server, self.attribute, self.value)

    def get_value(self):
        return self.value

    def save_value(self, value):
        # Normally, there shouldn't be any transformation necessary.
        self.value = value
        self.full_clean()
        self.save()

    @staticmethod
    def get_model(attribute_type):
        if attribute_type in 'string':
            return ServerStringAttribute
        if attribute_type == 'hostname':
            return ServerHostnameAttribute
        if attribute_type == 'boolean':
            return ServerBooleanAttribute
        if attribute_type == 'number':
            return ServerNumberAttribute
        if attribute_type == 'inet':
            return ServerInetAttribute
        if attribute_type == 'macaddr':
            return ServerMACAddressAttribute
        if attribute_type == 'date':
            return ServerDateAttribute


class ServerStringAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='string'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_string_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )


class ServerHostnameAttributeManager(models.Manager):
    def get_queryset(self):
        manager = super(ServerHostnameAttributeManager, self)
        return manager.get_queryset().select_related('value')


class ServerHostnameAttribute(ServerAttribute):
    objects = ServerHostnameAttributeManager()

    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='hostname'),
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
        db_table = 'server_hostname_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )

    def get_value(self):
        return self.value.hostname

    def save_value(self, value):
        target_servertype = self.attribute.target_servertype

        try:
            target_server = Server.objects.get(hostname=value)
        except Server.DoesNotExist:
            raise ValidationError(
                'No server with hostname "{0}" exist.'.format(value)
            )

        if target_server.servertype != target_servertype:
            raise ValidationError(
                'Attribute "{0}" has to be from servertype "{1}".'
                .format(self.attribute, self.attribute.target_servertype)
            )

        # We are also going to check that the servers have the same
        # project, but only if this servertype doesn't have a fixed
        # project.
        if (
            not target_servertype.fixed_project and
            target_server.project != self.server.project
        ):
            raise ValidationError(
                'Attribute "{0}" has to be from the project {1}.'
                .format(self.attribute, self.server.project)
            )

        ServerAttribute.save_value(self, target_server)


class ServerBooleanAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='boolean'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_boolean_attribute'
        unique_together = (('server', '_attribute'), )
        index_together = (('_attribute', ), )

    def get_value(self):
        return True

    def save_value(self, value):
        if value:
            self.save()
        else:
            self.delete()


class ServerNumberAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='number'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = models.DecimalField(max_digits=65, decimal_places=0)

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_number_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )

    def get_value(self):
        return (
            int(self.value)
            if self.value.as_tuple().exponent == 0
            else float(self.value)
        )


class ServerInetAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='inet'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = netfields.InetAddressField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_inet_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )


class ServerMACAddressAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='macaddr'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = netfields.MACAddressField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_macaddr_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )


class ServerDateAttribute(ServerAttribute):
    _attribute = models.ForeignKey(
        Attribute,
        db_column='attribute_id',
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='date'),
    )
    attribute = Attribute.foreign_key_lookup('_attribute_id')
    value = models.DateField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_date_attribute'
        unique_together = (('server', '_attribute', 'value'), )
        index_together = (('_attribute', 'value'), )


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

    def __str__(self):
        return str(self.change_on)


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

    def __str__(self):
        return str(self.change_on)


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

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.hostname)


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

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.hostname)


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

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.hostname)


#
# Helper Functions
#
# They are not accepting or returning Model instances, otherwise they would
# better live inside the model.
#

def get_unused_ip_addrs(network_ip_addr):
    used = {i.ip for i in (
        Server.objects
        .filter(intern_ip__net_contained_or_equal=network_ip_addr)
        .order_by()     # Clear ordering for database performance
        .values_list('intern_ip', flat=True)
    )}
    for ip_addr in ip_network(network_ip_addr).hosts():
        if ip_addr not in used:
            yield ip_addr
