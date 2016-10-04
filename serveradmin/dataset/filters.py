from __future__ import unicode_literals

import re
import operator
from decimal import Decimal
from ipaddress import ip_interface, ip_network

from django.core.exceptions import ValidationError

from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import (
    Project,
    Segment,
    Servertype,
    Server,
    ServerAttribute,
)


class FilterValueError(ValidationError):
    pass


class BaseFilter(object):
    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)


class NoArgFilter(BaseFilter):
    def __repr__(self):
        return '{0}()'.format(type(self).__name__)

    def __eq__(self, other):
        return isinstance(other, type(self))

    def __hash__(self):
        return hash(type(self).__name__)

    def typecast(self, attribute):
        # We don't have values to typecast
        pass

    def matches(self, value):
        return self.filt.matches(value)

    def as_code(self):
        return 'filters.{0}()'.format(type(self).__name__)

    @classmethod
    def from_obj(cls, obj):
        return cls()


class NetworkFilter(BaseFilter):
    def typecast(self, attribute):
        # We don't really need to cast anything.  The child classes
        # can do that on their __init__() methods as they cannot be
        # initialised anything other than Network objects.  In here,
        # we took our chance to validate the attribute.
        if attribute.type != 'ip':
            raise FilterValueError(
                'Only IP addresses can be used by this filter.'
            )


# We need this class to group optional filters.
class OptionalFilter(BaseFilter):
    pass


class ExactMatch(BaseFilter):
    def __init__(self, value):
        self.value = value
        self.network = '/' in str(value)

    def __repr__(self):
        return 'ExactMatch({0!r})'.format(self.value)

    def __eq__(self, other):
        if isinstance(other, ExactMatch):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash('ExactMatch') ^ hash(self.value)

    def typecast(self, attribute):
        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, attribute, servertypes):
        if attribute.type == 'boolean' and not self.value:
            return 'NOT ' + _condition_sql(attribute, "{0} = '1'", servertypes)

        template = '{0} = ' + value_to_sql(attribute, self.value)

        if attribute.pk == 'intern_ip':
            template += ' AND servertype_id IN ({0})'.format(', '.join(
                "'{0}'".format(s.pk)
                for s in Servertype.objects.all()
                if (s.ip_addr_type == 'network') == self.network
            ))

        return _condition_sql(attribute, template, servertypes)

    def matches(self, value):
        return value == self.value

    def as_code(self):
        return repr(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise FilterValueError('Invalid object for ExactMatch')


class Regexp(BaseFilter):
    def __init__(self, regexp):
        try:
            self._regexp_obj = re.compile(regexp)
        except re.error as e:
            raise FilterValueError('Invalid regexp: ' + str(e))

        self.regexp = regexp

    def __repr__(self):
        return 'Regexp({0!r})'.format(self.regexp)

    def __eq__(self, other):
        if isinstance(other, Regexp):
            return self.regexp == other.regexp
        return False

    def __hash__(self):
        return hash('Regexp') ^ hash(self.regexp)

    def typecast(self, attribute):
        # Regexp value is always string, no need to typecast
        pass

    def as_sql_expr(self, attribute, servertypes):
        value = raw_sql_escape(self.regexp)

        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            template = (
                '{{0}} IN ('
                '   SELECT server_id'
                '   FROM server'
                '   WHERE hostname ~ E{0}'
                ')'
                .format(value)
            )
        else:
            template = '{{0}} ~ E{0}'.format(value)

        return _condition_sql(attribute, template, servertypes)

    def matches(self, value):
        return bool(self._regexp_obj.search(str(value)))

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'regexp' in obj and isinstance(obj['regexp'], basestring):
            return cls(obj['regexp'])
        raise FilterValueError('Invalid object for Regexp')


class Comparison(BaseFilter):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise FilterValueError(
                'Invalid comparison operator: ' + comparator
            )
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparison({0!r}, {1!r})'.format(self.comparator, self.value)

    def __eq__(self, other):
        if isinstance(other, Comparison):
            return (self.comparator == other.comparator and
                    self.value == other.value)
        return False

    def __hash__(self):
        return hash('Comparison') ^ hash(self.comparator) ^ hash(self.value)

    def typecast(self, attribute):
        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            raise FilterValueError('Hostnames cannot be compared.')

        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, attribute, servertypes):
        return _condition_sql(attribute, '{{0}} {0} {1}'.format(
            self.comparator, value_to_sql(attribute, self.value), servertypes
        ))

    def matches(self, value):
        if self.comparator == '<':
            op = operator.lt
        elif self.comparator == '>':
            op = operator.gt
        elif self.comparator == '<=':
            op = operator.le
        elif self.comparator == '>=':
            op = operator.gt
        else:
            raise FilterValueError("Operator doesn't exists")

        return op(value, self.value)

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'comparator' in obj and 'value' in obj:
            return cls(obj['comparator'], obj['value'])
        raise FilterValueError('Invalid object for Comparison')


class Any(BaseFilter):
    def __init__(self, *values):
        self.values = set(flatten(values))

    def __repr__(self):
        return 'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def __eq__(self, other):
        if isinstance(other, Any):
            return self.values == other.values
        return False

    def __hash__(self):
        h = hash('Any')
        for val in self.values:
            h ^= hash(val)
        return h

    def typecast(self, attribute):
        self.values = set(
            typecast(attribute, x, force_single=True)
            for x in self.values
        )

    def as_sql_expr(self, attribute, servertypes):
        if not self.values:
            return '0 = 1'

        return _condition_sql(attribute, '{{0}} IN ({0})'.format(
            ', '.join(value_to_sql(attribute, v) for v in self.values)
        ), servertypes)

    def matches(self, value):
        return value in self.values

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'values' in obj and isinstance(obj['values'], list):
            return cls(*obj['values'])
        raise FilterValueError('Invalid object for Any')


class _AndOr(BaseFilter):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = ', '.join(repr(filt) for filt in self.filters)

        return '{0}({1})'.format(type(self), args)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.filters == other.filters

        return False

    def __hash__(self):
        result = hash(type(self))
        for value in self.filters:
            result ^= hash(value)

        return result

    def typecast(self, attribute):
        for filt in self.filters:
            filt.typecast(attribute)

    def as_sql_expr(self, attribute, servertypes):
        joiner = ' {0} '.format(type(self).__name__.upper())

        return '({0})'.format(joiner.join(
            v.as_sql_expr(attribute, servertypes) for v in self.filters
        ))

    def as_code(self):
        args = ', '.join(filt.as_code() for filt in self.filters)

        return 'filters.{0}({1})'.format(type(self), args)

    @classmethod
    def from_obj(cls, obj):
        if 'filters' in obj and isinstance(obj['filters'], list):
            if not obj['filters']:
                raise FilterValueError('Empty filters for And/Or')

            return cls(*[filter_from_obj(filter) for filter in obj['filters']])

        raise FilterValueError('Invalid object for {0}'.format(cls.__name__))


class And(_AndOr):
    def matches(self, value):
        for filter in self.filters:
            if not filter.matches(value):
                return False
        return True


class Or(_AndOr):
    def matches(self, value):
        for filter in self.filters:
            if filter.matches(value):
                return True
        return False


class Between(BaseFilter):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Between({0!r}, {1!r})'.format(self.a, self.b)

    def __eq__(self, other):
        if isinstance(other, Between):
            return self.a == other.a and self.b == other.b
        return False

    def __hash__(self):
        return hash('Between') ^ hash(self.a) ^ hash(self.b)

    def typecast(self, attribute):
        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            raise FilterValueError('Hostnames cannot be compared.')

        self.a = typecast(attribute, self.a, force_single=True)
        self.b = typecast(attribute, self.b, force_single=True)

    def as_sql_expr(self, attribute, servertypes):
        return _condition_sql(attribute, '{{0}} BETWEEN {0} AND {1}'.format(
            value_to_sql(attribute, self.a), value_to_sql(attribute, self.b)
        ), servertypes)

    def matches(self, value):
        return self.a <= value <= self.b

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'a' in obj and 'b' in obj:
            return cls(obj['a'], obj['b'])

        raise FilterValueError('Invalid object for Between')


class Not(BaseFilter):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Not({0})'.format(self.filter)

    def __eq__(self, other):

        if isinstance(other, Not):
            return self.filter == other.filter

        return False

    def __hash__(self):
        return hash('Not') ^ hash(self.filter)

    def typecast(self, attribute):
        self.filter.typecast(attribute)

    def as_sql_expr(self, attribute, servertypes):
        return 'NOT ({0})'.format(self.filter.as_sql_expr(
            attribute, servertypes
        ))

    def matches(self, value):
        return not self.filter.matches(value)

    def as_code(self):
        return 'filters.Not({0})'.format(self.filter.as_code())

    @classmethod
    def from_obj(cls, obj):

        if 'filter' in obj:
            return cls(filter_from_obj(obj['filter']))

        raise FilterValueError('Invalid object for Not')


class Startswith(BaseFilter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Startswith({0!})'.format(self.value)

    def __eq__(self, other):
        if isinstance(other, Startswith):
            return self.value == other.value

    def __hash__(self):
        return hash('Startswith') ^ hash(self.value)

    def typecast(self, attribute):
        self.value = str(self.value)

    def as_sql_expr(self, attribute, servertypes):
        value = self.value.replace('_', '\\_').replace('%', '\\%%')
        value = raw_sql_escape(value + '%%')

        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            template = (
                '{{0}} IN ('
                '   SELECT server_id'
                '   FROM server'
                '   WHERE hostname LIKE {0}'
                ')'
                .format(value),
            )
        else:
            template = '{0} LIKE ' + value

        return _condition_sql(attribute, template, servertypes)

    def matches(self, value):
        return str(value).startswith(self.value)

    def as_code(self):
        return 'filters.Startswith({0!r})'.format(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj and isinstance(obj['value'], basestring):
            return cls(obj['value'])
        raise FilterValueError('Invalid object for Startswith')


class Overlap(NetworkFilter):
    def __init__(self, *networks):
        try:
            self.networks = [ip_network(n) for n in networks]
        except ValueError as error:
            raise FilterValueError(str(error))

    def __repr__(self):
        return '{0}({1})'.format(
            type(self), ', '.join(repr(n) for n in self.networks)
        )

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return all(
                n1 == n2 for n1, n2 in zip(self.networks, other.networks)
            )
        return False

    def __hash__(self):
        result = hash(type(self))
        for network in self.networks:
            result ^= hash(network)
        return result

    def as_sql_expr(self, attribute, servertypes):
        return _condition_sql(attribute, "{{0}} && ANY('{{{{{0}}}}}')".format(
            ','.join(str(n) for n in self.networks)
        ), servertypes)

    def matches(self, value):
        return any(value in n for n in self.networks)

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj['networks'])
        raise FilterValueError('Invalid object for {0}'.format(cls))


class InsideNetwork(Overlap):
    def as_sql_expr(self, attribute, servertypes):
        return _condition_sql(attribute, "{{0}} <<= ANY('{{{{{0}}}}}')".format(
            ','.join(str(n) for n in self.networks)
        ), servertypes)


class InsideOnlyNetwork(InsideNetwork):
    def as_sql_expr(self, attribute, servertypes):
        network_sql_array = "'{{{{{0}}}}}'".format(
            ','.join(str(n) for n in self.networks)
        )
        return _condition_sql(attribute, (
            '{{0}} << ANY({0}) AND NOT EXISTS ('
            '   SELECT 1 '
            '   FROM server AS supernet '
            '   WHERE {{0}} << supernet.intern_ip AND '
            '       supernet.intern_ip << ANY({0})'
            ')'
            .format(network_sql_array)
        ), servertypes)


class PrivateIP(NetworkFilter, NoArgFilter):
    blocks = (
        ip_network('10.0.0.0/8'),
        ip_network('172.16.0.0/12'),
        ip_network('192.168.0.0/16'),
    )

    def __init__(self):
        self.filt = InsideNetwork(*PrivateIP.blocks)

    def as_sql_expr(self, attribute, servertypes):
        return self.filt.as_sql_expr(attribute, servertypes)


class PublicIP(NetworkFilter, NoArgFilter):
    def __init__(self):
        self.filt = Not(InsideNetwork(*PrivateIP.blocks))

    def as_sql_expr(self, attribute, servertypes):
        return self.filt.as_sql_expr(attribute, servertypes)


class Optional(OptionalFilter):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Optional({0!r})'.format(self.filter)

    def __eq__(self, other):
        if isinstance(other, Optional):
            return self.filter == other.filter
        return False

    def __hash__(self):
        return hash('Optional') ^ hash(self.filter)

    def typecast(self, attribute):
        self.filter.typecast(attribute)

    def as_sql_expr(self, attribute, servertypes):
        return self.filter.as_sql_expr(attribute, servertypes)

    def matches(self, value):
        if value is None:
            return True
        return self.filter.matches(value)

    def as_code(self):
        return 'filters.Optional({0})'.format(self.filter.as_code())

    @classmethod
    def from_obj(cls, obj):

        if 'filter' in obj:
            return cls(filter_from_obj(obj['filter']))

        raise FilterValueError('Invalid object for Optional')


class Empty(OptionalFilter):
    def __repr__(self):
        return 'Empty()'

    def __eq__(self, other):
        return isinstance(other, Empty)

    def __hash__(self):
        return hash('Empty')

    def typecast(self, attribute):
        pass

    def as_sql_expr(self, attribute, servertypes):
        return 'NOT ' + _condition_sql(
            attribute, '{0} IS NOT NULL', servertypes
        )

    def matches(self, value):
        return value is None

    def as_code(self):
        return 'filters.Empty()'

    @classmethod
    def from_obj(cls, obj):
        return cls()


def _prepare_filter(filter):
    return filter if isinstance(filter, BaseFilter) else ExactMatch(filter)


def filter_from_obj(obj):
    if not (isinstance(obj, dict) and
            'name' in obj and
            isinstance(obj['name'], basestring)):
        raise FilterValueError('Invalid filter object')

    try:
        return filter_classes[obj['name']].from_obj(obj)
    except KeyError:
        raise FilterValueError('No such filter: {0}'.format(obj['name']))


filter_classes = {
    'exactmatch': ExactMatch,
    'regexp': Regexp,
    'comparison': Comparison,
    'any': Any,
    'any': Any,
    'and': And,
    'or': Or,
    'between': Between,
    'not': Not,
    'startswith': Startswith,
    'overlap': Overlap,
    'insidenetwork': InsideNetwork,
    'privateip': PrivateIP,
    'publicip': PublicIP,
    'optional': Optional,
    'empty': Empty,
}


def value_to_sql(attribute, value):
    # Validations of special relation attributes
    if attribute.pk == 'servertype':
        try:
            Servertype.objects.get(pk=value)
        except Servertype.DoesNotExist:
            raise FilterValueError('Invalid servertype: ' + value)
    elif attribute.pk == 'segment':
        try:
            Segment.objects.get(pk=value)
        except Segment.DoesNotExist:
            raise FilterValueError('Invalid segment: ' + value)
    elif attribute.pk == 'project':
        try:
            Project.objects.get(pk=value)
        except Project.DoesNotExist:
            raise FilterValueError('Invalid project: ' + value)

    if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
        try:
            return str(Server.objects.get(hostname=value).server_id)
        except Server.DoesNotExist as error:
            raise FilterValueError(str(error))

    if attribute.type == 'number':
        return str(Decimal(value))

    # Those needs to be quoted, because they are stored as string on
    # the database.
    if attribute.type == 'boolean':
        return raw_sql_escape(1 if value else 0)
    if attribute.type == 'integer':
        return raw_sql_escape(int(value))
    if attribute.type == 'ipv6':
        return raw_sql_escape(
            ''.join('{:02x}'.format(x) for x in ip_interface(value).packed)
        )
    return raw_sql_escape(value)


def _condition_sql(attribute, template, servertypes):
    assert servertypes

    if attribute.special:
        field = attribute.special.field
        if field.startswith('_'):
            field = field[1:]

        return template.format('server.' + field)

    if attribute.type == 'supernet':
        return _exists_sql('server', 'sub', (
            "sub.servertype_id = '{0}'".format(attribute.target_servertype.pk),
            'sub.intern_ip >>= server.intern_ip',
            template.format('sub.server_id'),
        ))

    rel_table = ServerAttribute.get_model('hostname')._meta.db_table

    if attribute.type == 'reverse_hostname':
        return _exists_sql(rel_table, 'sub', (
            "sub.attribute_id = '{0}'".format(attribute.reversed_attribute.pk),
            'sub.value = server.server_id',
            template.format('sub.server_id'),
        ))

    # We must have handled the virtual attribute types.
    assert attribute.can_be_materialized()

    # We start with the condition for the attributes the server has on
    # its own.  Then, add the conditions for all possible relations.  They
    # are going to be OR'ed together.
    relation_conditions = []
    related_via_attributes = set()
    other_servertypes = list()
    for sa in attribute.servertype_attributes.filter(
        _servertype__in=servertypes
    ):
        if sa.related_via_attribute:
            related_via_attributes.add(sa.related_via_attribute)
        else:
            other_servertypes.append(sa.servertype)
    for related_via_attribute in related_via_attributes:
        related_via_servertypes = tuple(
            sa.servertype
            for sa in related_via_attribute.servertype_attributes.filter(
                _servertype__in=servertypes
            )
        )
        assert related_via_servertypes
        if related_via_attribute.type == 'supernet':
            relation_condition = _exists_sql('server', 'rel1', (
                "rel1.servertype_id = '{0}'".format(
                    related_via_attribute.target_servertype.pk
                ),
                'rel1.intern_ip >>= server.intern_ip',
                'rel1.server_id = sub.server_id',
            ))
        elif related_via_attribute.type == 'reverse_hostname':
            relation_condition = _exists_sql(rel_table, 'rel1', (
                "rel1.attribute_id = '{0}'".format(
                    related_via_attribute.reversed_attribute.pk
                ),
                'rel1.value = server.server_id',
                'rel1.server_id = sub.server_id',
            ))
        else:
            assert related_via_attribute.type == 'hostname'
            relation_condition = _exists_sql(rel_table, 'rel1', (
                "rel1.attribute_id = '{0}'".format(related_via_attribute.pk),
                'rel1.server_id = server.server_id',
                'rel1.value = sub.server_id',
            ))
        relation_conditions.append(
            (relation_condition, related_via_servertypes)
        )
    if other_servertypes:
        relation_conditions.append(
            ('server.server_id = sub.server_id', other_servertypes)
        )
    assert relation_conditions

    table = ServerAttribute.get_model(attribute.type)._meta.db_table
    if len(relation_conditions) == 1:
        mixed_relation_condition = relation_conditions[0][0]
    else:
        mixed_relation_condition = '({0})'.format(' OR '.join(
            '({0} AND server.servertype_id IN ({1}))'
            .format(relation_condition, ', '.join(
                "'{0}'".format(s.pk) for s in servertypes)
            )
            for relation_condition, servertypes in relation_conditions
        ))

    return _exists_sql(table, 'sub', (
        mixed_relation_condition,
        "sub.attribute_id = '{0}'".format(attribute.pk),
        template.format('sub.value'),
    ))


def _exists_sql(table, alias, conditions):
    return 'EXISTS (SELECT 1 FROM {0} AS {1} WHERE {2})'.format(
        table, alias, ' AND '.join(conditions)
    )


def raw_sql_escape(value):
    try:
        value = str(value)
    except UnicodeEncodeError as error:
        raise FilterValueError(str(error))

    if "'" in value:
        raise FilterValueError('Single quote cannot be used')

    if value.endswith('\\'):
        raise FilterValueError('Escape character cannot be used in the end')

    value = value.replace('{', '{{').replace('}', '}}')

    return "'" + value + "'"


def flatten(values):
    for value in values:
        if isinstance(value, (tuple, list, set)):
            for subvalue in flatten(value):
                yield subvalue
        else:
            yield value
