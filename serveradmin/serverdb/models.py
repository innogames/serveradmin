"""Serveradmin - Core Models

Copyright (c) 2021 InnoGames GmbH
"""

import re
from distutils.util import strtobool
from ipaddress import (
    IPv4Address,
    IPv6Address,
    ip_interface,
    IPv4Interface,
    IPv6Interface,
    ip_network,
    IPv4Network,
    IPv6Network,
)
from typing import Union

import netfields
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.timezone import now
from django.utils.translation import gettext as _
from netaddr import EUI

from adminapi.datatype import STR_BASED_DATATYPES
from serveradmin.apps.models import Application

ATTRIBUTE_TYPES = {
    'string': str,
    'boolean': lambda x: bool(strtobool(x)),
    'relation': str,
    'reverse': str,
    'number': lambda x: float(x) if '.' in str(x) else int(x),
    'inet': lambda x: inet_to_python(x),
    'macaddr': EUI,
    'date': str,
    'datetime': str,
    'supernet': str,
    'domain': str,
}

IP_ADDR_TYPES = [
    ('null', 'null: intern_ip must be empty, no inet attributes'),
    ('host', 'host: intern_ip and inet must be an ip address and unique across all objects per attribute'),
    ('loadbalancer', 'loadbalancer: intern_ip and inet must be an ip address'),
    ('network', 'network: intern_ip and inet must be an ip network, not overlapping with same servertype'),
]

LOOKUP_ID_VALIDATORS = [
    RegexValidator(r'\A[a-z][a-z0-9_]+\Z', 'Invalid id'),
]

HOSTNAME_VALIDATORS = [
    RegexValidator(
        r'\A(\*\.)?([a-z0-9]+(\.|-+))*[a-z0-9]+\Z', 'Invalid hostname'
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


# TODO: Make validators out of the methods is_ip_address, is_unique and
#       is_network and attach them to the model fields validators.
def is_ip_address(ip_interface: Union[IPv4Interface, IPv6Interface]) -> None:
    """Validate if IPv4/IPv6 address

    Raises a ValidationError if the ip_address is not an IPv4 or IPv6Address

    :param ip_interface:
    :return:
    """
    prefix_length = ip_interface.network.prefixlen
    max_prefix_length = ip_interface.network.max_prefixlen

    if prefix_length != max_prefix_length:
        raise ValidationError(
            'Netmask length must be {0}'.format(max_prefix_length))


def is_unique_ip(ip_interface: Union[IPv4Interface, IPv6Interface],
                 object_id: int,
                 attribute_id: str = None) -> None:
    """Validate if IPv4/IPv6 address is unique

    Raises a ValidationError if intern_ip or any other attribute of type inet
    with this ip_address already exists.

    :param ip_interface:
    :param object_id:
    :param attribute_id:
    :return:
    """

    # We avoid querying the duplicate hosts here and giving the user
    # detailed information because checking with exists is cheaper than
    # querying the server and this is a validation and should be fast.

    # Always exclude the current object_id from the query because we allow
    # duplication of data between the legacy (intern_ip, primary_ip6) and
    # the modern (ipv4, ipv6) attributes.

    # When operating on real attributes (not on intern_ip) find duplicates
    # only withing the same attribute id. That means different hosts can have
    # the same IP address as long as it is in different attributes.

    # TODO: Make "aid" mandatory when intern_ip is gone.
    if attribute_id:
        object_attribute_condition = Q(server_id=object_id) | ~Q(attribute_id=attribute_id)
    else:
        object_attribute_condition = Q(server_id=object_id)

    has_duplicates = (
        # TODO: Remove intern_ip.
        Server.objects.filter(intern_ip=ip_interface).exclude(
            Q(servertype__ip_addr_type='network') |
            Q(server_id=object_id)
        ).exists() or
        ServerInetAttribute.objects.filter(value=ip_interface).exclude(
            Q(server__servertype__ip_addr_type='network') | object_attribute_condition
        ).exists()
    )
    if has_duplicates:
        raise ValidationError(
            'An object with {0} already exists'.format(str(ip_interface)))


def is_network(ip_interface: Union[IPv4Interface, IPv6Interface]) -> None:
    """Validate if IPv4/IPv6 interface is a network

    Raise ValidationError if the given ip_interface is not a valid ip network.
    Mind that e.g. 192.168.0.1 or 192.168.0.1/32 are valid ip networks.

    :param ip_interface:
    :return:
    """

    try:
        ip_network(ip_interface)
    except ValueError as error:
        raise ValidationError(str(error))


def inet_to_python(obj: object) -> Union[IPv4Interface, IPv6Interface]:
    """Transform object to Python IPv4/IPv6Interface

    :param obj:
    :return:
    """

    # TODO: When refactoring the validation this can be a to_python method
    #       of the inet field.
    try:
        return ip_interface(obj)
    except ValueError as error:
        raise ValidationError(str(error))


def network_overlaps(ip_interface: Union[IPv4Interface, IPv6Interface],
                     servertype_id: str, object_id: int) -> None:
    """Validate if network overlaps with other objects of the servertype_id

    Raises a ValidationError if the ip network overlaps with any other existing
    objects network of the given servertype.

    :param ip_interface:
    :param servertype_id:
    :param object_id:
    :return:
    """

    overlaps = (
        Server.objects.filter(
            servertype=servertype_id,
            intern_ip__net_overlaps=ip_interface
        ).exclude(
            server_id=object_id
        ).exists() or
        # TODO: We should filter for attribute id here as well to have
        # consistent bebaviour with ip_addr_type: host and is_unique.
        ServerInetAttribute.objects.filter(
            server__servertype=servertype_id,
            value__net_overlaps=ip_interface
        ).exclude(
            server_id=object_id
        ).exists()
    )
    if overlaps:
        raise ValidationError(
            '{0} overlaps with network of another object'.format(
                str(ip_interface)))


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
        choices=IP_ADDR_TYPES,
    )

    class Meta:
        app_label = 'serverdb'
        db_table = 'servertype'
        ordering = ['servertype_id']

    def __str__(self):
        return self.servertype_id

class InetAddressFamilyChoice(models.TextChoices):
    IPV4 = 'IPV4', _('IPv4')
    IPV6 = 'IPV6', _('IPv6')
    __empty__ = _("none or any")

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
    inet_address_family = models.CharField(choices=InetAddressFamilyChoice.choices, max_length=5, blank=True)
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
    history = models.BooleanField(
        null=False, default=True,
        help_text='Log changes to this attribute')
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
        max_length=254, unique=True, validators=HOSTNAME_VALIDATORS
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

    def clean(self):
        super(Server, self).clean()

        ip_addr_type = self.servertype.ip_addr_type
        if ip_addr_type == 'null':
            if self.intern_ip is not None:
                raise ValidationError(
                    _('intern_ip must be null'), code='invalid value')
        else:
            # This is special to intern_ip for inet attributes this is covered
            # by making them required.
            if self.intern_ip is None:
                raise ValidationError(
                    _('intern_ip must not be null'), code='missing value')

            # TODO: This logic is duplicated to the ServerInetAttribute clean
            #       method but can be removed when we remove the special
            #       intern_ip.
            if type(self.intern_ip) not in [IPv4Interface, IPv6Interface]:
                self.intern_ip = inet_to_python(self.intern_ip)

            if ip_addr_type == 'host':
                is_ip_address(self.intern_ip)
                is_unique_ip(self.intern_ip, self.server_id)
            elif ip_addr_type == 'loadbalancer':
                is_ip_address(self.intern_ip)
            elif ip_addr_type == 'network':
                is_network(self.intern_ip)
                network_overlaps(self.intern_ip, self.servertype.servertype_id,
                                 self.server_id)

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
        if attribute_type == 'datetime':
            return ServerDateTimeAttribute


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
        return manager.get_queryset().prefetch_related('value')


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
        try:
            target_server = Server.objects.get(hostname=value)
        except Server.DoesNotExist:
            raise ValidationError(
                'No server with hostname "{0}" exist.'.format(value)
            )

        target_servertype = self.attribute.target_servertype
        if target_servertype and target_server.servertype != target_servertype:
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

    def clean(self):
        super(ServerAttribute, self).clean()

        if self.attribute.inet_address_family == InetAddressFamilyChoice.IPV4:
            allowed_types = (IPv4Interface,)
        elif self.attribute.inet_address_family == InetAddressFamilyChoice.IPV6:
            allowed_types = (IPv6Interface,)
        else:
            allowed_types = (IPv4Interface, IPv6Interface)

        if type(self.value) not in allowed_types:
            self.value = inet_to_python(self.value)
            if type(self.value) not in allowed_types:
                raise ValidationError(
                    f'IP address {self.value} is not '
                    f'of type {self.attribute.get_inet_address_family_display()}!'
                )

        # Get the ip_addr_type of the servertype
        ip_addr_type = self.server.servertype.ip_addr_type

        if ip_addr_type == 'null':
            # A Servertype with ip_addr_type "null" and attributes of type
            # inet must be denied per configuration. This is just a safety net
            # in case e.g. somebody creates them programmatically.
            raise ValidationError(
                _('%(attribute_id)s must be null'), code='invalid value',
                params={'attribute_id': self.attribute_id})
        elif ip_addr_type == 'host':
            is_ip_address(self.value)
            is_unique_ip(self.value, self.server.server_id, self.attribute_id)
        elif ip_addr_type == 'loadbalancer':
            is_ip_address(self.value)
        elif ip_addr_type == 'network':
            is_network(self.value)
            network_overlaps(self.value, self.server.servertype_id,
                             self.server.server_id)


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


class ServerDateTimeAttribute(ServerAttribute):
    attribute = models.ForeignKey(
        Attribute,
        db_index=False,
        on_delete=models.CASCADE,
        limit_choices_to=dict(type='datetime'),
    )
    value = models.DateTimeField()

    class Meta:
        app_label = 'serverdb'
        db_table = 'server_datetime_attribute'
        unique_together = [['server', 'attribute', 'value']]
        index_together = [['attribute', 'value']]


class ChangeCommit(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    app = models.ForeignKey(Application, null=True, on_delete=models.PROTECT)
    change_on = models.DateTimeField(default=now, db_index=True)

    class Meta:
        app_label = 'serverdb'

    def __str__(self):
        return str(self.change_on)


class Change(models.Model):
    class Type(models.TextChoices):
        CREATE = 'create', _('create')
        CHANGE = 'change', _('change')
        DELETE = 'delete', _('delete')

    class ChangeJSONEncoder(DjangoJSONEncoder):
        _NETWORK_TYPES = (
            IPv4Address,
            IPv6Address,
            IPv4Network,
            IPv6Network,
            EUI,
        )

        # This is close to json_encode_extra used in adminapi.request but with
        # two differences. First we don't need to take care about BaseFilter
        # objects as they are already "resolved". Second DjangoJSONEncoder
        # handles datetime on its own. Third we don't blindly cast everything
        # else to string but explicitly check for the types we now and fail
        # for the others.
        def default(self, obj):
            # Handles ServerInetAttribute and ServerMACAddressAttribute values
            if isinstance(obj, self._NETWORK_TYPES):
                return str(obj)
            # Handles MultiAttr values
            elif isinstance(obj, set):
                return list(obj)

            return super().default(obj)

    object_id = models.IntegerField(db_index=True)
    # XXX: Add migration with PostgreSQL native enum
    change_type = models.CharField(choices=Type.choices, max_length=6)
    change_json = models.JSONField(encoder=ChangeJSONEncoder)
    commit = models.ForeignKey(ChangeCommit, on_delete=models.CASCADE)

    class Meta:
        app_label = 'serverdb'
