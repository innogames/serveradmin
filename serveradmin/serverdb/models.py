"""Serveradmin - Core Models

Copyright (c) 2018 InnoGames GmbH
"""

import re
import json

from distutils.util import strtobool
from ipaddress import ip_address, ip_network

from netaddr import EUI

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.timezone import now
from django.contrib.auth.models import User

import netfields

from adminapi.datatype import STR_BASED_DATATYPES
from serveradmin.apps.models import Application

ATTRIBUTE_TYPES = {
    'string': str,
    'boolean': lambda x: bool(strtobool(x)),
    'relation': str,
    'reverse': str,
    'number': lambda x: float(x) if '.' in str(x) else int(x),
    'inet': lambda x: ip_network(x) if '/' in str(x) else ip_address(x),
    'macaddr': EUI,
    'date': str,
    'supernet': str,
    'domain': str,
}

IP_ADDR_TYPES = (
    'null',
    'host',
    'loadbalancer',
    'network',
)

LOOKUP_ID_VALIDATORS = [
    RegexValidator(r'\A[a-z][a-z0-9_]+\Z', 'Invalid id'),
]

HOSTNAME_VALIDATORS = [
    RegexValidator(
        r'\A(\*\.)?([a-z0-9]+[\.\-])*[a-z0-9]+\Z', 'Invalid hostname'
    ),
]

REGEX_VALIDATORS = [
    RegexValidator(
        r'\A\\A.*\\Z\Z',
        'You must wrap your pattern in "\\A" and "\\Z" to force line matching'
    ),
]


def get_choices(types):
    # Django allows the choices to be stored and named differently,
    # but we don't need it.  We are zipping the tuple to itself
    # to use the same names.
    return zip(*([types] * 2))


class Servertype(models.Model):
    servertype_id = models.CharField(
        max_length=32,
        primary_key=True,
        db_index=False,
        validators=LOOKUP_ID_VALIDATORS,
    )
    description = models.CharField(max_length=1024)
    ip_addr_type = models.CharField(
        max_length=32,
        choices=get_choices(IP_ADDR_TYPES),
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'
        ordering = ['servertype_id']

    def __str__(self):
        return self.servertype_id


class Attribute(models.Model):
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
        validators=LOOKUP_ID_VALIDATORS,
    )
    type = models.CharField(
        max_length=32,
        choices=get_choices(ATTRIBUTE_TYPES.keys()),
    )
    multi = models.BooleanField(null=False, default=False)
    hovertext = models.TextField(null=False, blank=True, default='')
    group = models.CharField(
        max_length=32, null=False, blank=False, default='other'
    )
    help_link = models.CharField(max_length=255, blank=True, null=True)
    readonly = models.BooleanField(null=False, default=False)
    target_servertype = models.ForeignKey(
        Servertype, on_delete=models.CASCADE,
        db_index=False, null=True, blank=True
    )
    reversed_attribute = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        related_name='reversed_attribute_set',
        null=True,
        blank=True,
        db_index=False,
        limit_choices_to=dict(type='relation'),
    )
    clone = models.BooleanField(null=False, default=False)
    regexp = models.CharField(max_length=1024, validators=REGEX_VALIDATORS)
    _compiled_regexp = None

    class Meta:
        app_label = 'serverdb'
        db_table = 'attribute'
        ordering = ['attribute_id']

    def __str__(self):
        return self.attribute_id

    def initializer(self):
        if self.multi:
            return set
        if self.type == 'boolean':
            return bool
        return lambda: None

    def from_str(self, value):
        if self.multi and not isinstance(value, (list, set)):
            raise ValidationError('Attr is multi, but value is not a list/set')

        if value is None:
            return value

        from_str_fn = ATTRIBUTE_TYPES[self.type]
        try:
            if self.multi:
                return set(from_str_fn(x) for x in value)
            return from_str_fn(value)
        except ValueError as error:
            raise ValidationError(str(error))

    def _get_compiled_regexp(self):
        if not self._compiled_regexp and self.regexp is not None:
            self._compiled_regexp = re.compile(self.regexp)

        return self._compiled_regexp

    def regexp_match(self, value):
        re_compiled = self._get_compiled_regexp()
        if re_compiled is None:
            raise ValidationError(
                'Attribute {} has no value validation regexp set'
                .format(self.attribute_id)
            )

        # We use lower case booleans in our regexes but python __str__ methods
        # on booleans return them in upper case.
        if isinstance(value, bool):
            value = str(value).lower()
        else:
            value = str(value)

        return re_compiled.match(value)

    def clean(self):
        if self.regexp == '':
            self.regexp = None
        super(Attribute, self).clean()


class ServerTableSpecial(object):
    def __init__(self, field, unique=False):
        self.field = field
        self.unique = unique


Attribute.specials = {
    'object_id': Attribute(
        attribute_id='object_id',
        type='number',
        multi=False,
        clone=False,
        group='base',
        special=ServerTableSpecial('server_id'),
    ),
    'hostname': Attribute(
        attribute_id='hostname',
        type='string',
        multi=False,
        clone=True,
        group='base',
        special=ServerTableSpecial('hostname', unique=True),
    ),
    'servertype': Attribute(
        attribute_id='servertype',
        type='string',
        multi=False,
        clone=True,
        group='base',
        special=ServerTableSpecial('servertype_id'),
    ),
    'intern_ip': Attribute(
        attribute_id='intern_ip',
        type='inet',
        multi=False,
        clone=True,
        group='base',
        special=ServerTableSpecial('intern_ip'),
    ),
}


class ServertypeAttribute(models.Model):
    servertype = models.ForeignKey(
        Servertype,
        related_name='attributes',
        db_index=False,
        on_delete=models.CASCADE,
    )
    attribute = models.ForeignKey(
        Attribute,
        related_name='servertype_attributes',
        db_index=False,
        on_delete=models.CASCADE,
    )
    related_via_attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE,
        related_name='related_via_servertype_attributes',
        null=True,
        blank=True,
        db_index=False,
        # It can only be related via a relation (AKA as an hostname
        # attribute).
        limit_choices_to=models.Q(
            type__in=['relation', 'reverse', 'supernet', 'domain']
        ),
    )
    consistent_via_attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE,
        related_name='consistent_via_servertype_attributes',
        null=True,
        blank=True,
        db_column='consistent_via_attribute_id',
        db_index=False,
    )
    required = models.BooleanField(null=False, default=False)
    default_value = models.CharField(max_length=255, null=True, blank=True)
    default_visible = models.BooleanField(null=False, default=False)

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype_attribute'
        ordering = ['servertype', 'attribute']
        unique_together = [['servertype', 'attribute']]

    def __str__(self):
        return '{0} - {1}'.format(self.servertype, self.attribute)

    def get_default_value(self):
        if not self.default_value:
            return self.attribute.initializer()()

        if self.attribute.multi:
            default_value = self.default_value.split(',')
        else:
            default_value = self.default_value

        return self.attribute.from_str(default_value)

    def clean(self):
        if self.default_value == '':
            self.default_value = None
        super(ServertypeAttribute, self).clean()


class Server(models.Model):
    """Servers are the main objects of the system.  They are stored in
    entity-attribute-value schema.  There are multiple models to store
    the attribute values of the servers by different data types.
    """
    objects = netfields.NetManager()

    server_id = models.AutoField(primary_key=True)
    hostname = models.CharField(
        max_length=64, unique=True, validators=HOSTNAME_VALIDATORS
    )
    intern_ip = netfields.InetAddressField(null=True, blank=True)
    servertype = models.ForeignKey(Servertype, on_delete=models.PROTECT)

    class Meta:
        app_label = 'serverdb'
        db_table = 'server'

    def __str__(self):
        return self.hostname

    def get_supernet(self, servertype):
        return Server.objects.get(
            servertype=servertype,
            intern_ip__net_contains_or_equals=self.intern_ip,
        )

    def clean(self, *args, **kwargs):
        super(Server, self).clean(*args, **kwargs)
        if self.servertype.ip_addr_type == 'null':
            if self.intern_ip is not None:
                raise ValidationError('IP address must be null.')
        else:
            if self.intern_ip is None:
                raise ValidationError('IP address must not be null.')

            if self.servertype.ip_addr_type == 'network':
                self._validate_network_intern_ip()
            else:
                self._validate_host_intern_ip()

    def _validate_host_intern_ip(self):
        if self.intern_ip.max_prefixlen != self.netmask_len():
            raise ValidationError(
                'Netmask length must be {0}.'
                .format(self.intern_ip.max_prefixlen)
            )

        # Check for other server with overlapping addresses
        for server in Server.objects.filter(
            intern_ip__net_overlaps=self.intern_ip
        ).exclude(server_id=self.server_id):
            if server.servertype.ip_addr_type == 'host':
                raise ValidationError(
                    'IP address already taken by the host "{0}".'
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
        ).exclude(server_id=self.server_id):
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
        return model.objects.filter(server=self, attribute=attribute)

    def add_attribute(self, attribute, value):
        model = ServerAttribute.get_model(attribute.type)
        if model is ServerBooleanAttribute and not value:
            return
        server_attribute = model(server=self, attribute=attribute)
        server_attribute.save_value(value)


class ServerAttribute(models.Model):
    server = models.ForeignKey(
        Server, db_index=False, on_delete=models.CASCADE
    )

    class Meta:
        abstract = True

    def __str__(self):
        return '{0}->{1}={2}'.format(
            self.server, self.attribute, self.get_value()
        )

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
        if attribute_type == 'relation':
            return ServerRelationAttribute
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
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='string'),
    )
    value = models.CharField(max_length=1024)

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_string_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]

    def save_value(self, value):
        for char in '\'"':
            if char in value:
                raise ValidationError(
                    '"{}" character is not allowed on string attributes'
                    .format(char)
                )
        for datatype, regexp in STR_BASED_DATATYPES:
            if regexp.match(value):
                raise ValidationError(
                    'String attribute value "{}" matches with {} type'
                    .format(value, datatype.__name__)
                )

        super().save_value(value)


class ServerRelationAttributeManager(models.Manager):
    def get_queryset(self):
        manager = super(ServerRelationAttributeManager, self)
        return manager.get_queryset().select_related('value')


class ServerRelationAttribute(ServerAttribute):
    objects = ServerRelationAttributeManager()

    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='relation'),
    )
    value = models.ForeignKey(
        Server,
        db_column='value',
        db_index=False,
        on_delete=models.PROTECT,
        related_name='relation_attribute_servers',
        related_query_name='relation_attribute_server',
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_relation_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]

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

        ServerAttribute.save_value(self, target_server)


class ServerBooleanAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='boolean'),
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_boolean_attribute'
        unique_together = [['server', 'attribute']]
        index_together = [['attribute']]

    def get_value(self):
        return True

    def save_value(self, value):
        if value:
            self.save()
        else:
            self.delete()


class ServerNumberAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='number'),
    )
    value = models.DecimalField(max_digits=65, decimal_places=0)

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_number_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]

    def get_value(self):
        return (
            int(self.value)
            if self.value.as_tuple().exponent == 0
            else float(self.value)
        )


class ServerInetAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='inet'),
    )
    value = netfields.InetAddressField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_inet_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]


class ServerMACAddressAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='macaddr'),
    )
    value = netfields.MACAddressField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_macaddr_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]


class ServerDateAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='date'),
    )
    value = models.DateField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_date_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]


class Change(models.Model):
    change_on = models.DateTimeField(default=now, db_index=True)
    user = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    app = models.ForeignKey(Application, null=True, on_delete=models.PROTECT)
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
    user = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    app = models.ForeignKey(Application, null=True, on_delete=models.PROTECT)

    class Meta:
        app_label = 'serverdb'

    def __str__(self):
        return str(self.change_on)


class ChangeDelete(models.Model):
    commit = models.ForeignKey(ChangeCommit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    attributes_json = models.TextField()

    class Meta:
        app_label = 'serverdb'
        unique_together = [['commit', 'server_id']]

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)


class ChangeUpdate(models.Model):
    commit = models.ForeignKey(ChangeCommit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    updates_json = models.TextField()

    class Meta:
        app_label = 'serverdb'
        unique_together = [['commit', 'server_id']]

    @property
    def updates(self):
        return json.loads(self.updates_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)


class ChangeAdd(models.Model):
    commit = models.ForeignKey(ChangeCommit, on_delete=models.CASCADE)
    server_id = models.IntegerField(db_index=True)
    attributes_json = models.TextField()

    class Meta:
        app_label = 'serverdb'
        unique_together = [['commit', 'server_id']]

    @property
    def attributes(self):
        return json.loads(self.attributes_json)

    def __str__(self):
        return '{0}: {1}'.format(str(self.commit), self.server_id)
