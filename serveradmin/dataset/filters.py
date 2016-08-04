import re
import operator
import time
import dateutil.parser
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address, ip_network

from django.core.exceptions import ValidationError

from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import (
    Project,
    Segment,
    Servertype,
    ServertypeAttribute,
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

    def matches(self, server_obj, attr_name):
        return self.filt.matches(server_obj, attr_name)

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

    def as_sql_expr(self, attribute):
        if attribute.type == 'boolean' and not self.value:
            return 'NOT ' + _condition_sql(attribute, "{0} = '1'")

        return _condition_sql(
            attribute, '{0} = ' + value_to_sql(attribute, self.value)
        )

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] == self.value

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
            raise FilterValueError('Invalid regexp: ' + unicode(e))

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

    def as_sql_expr(self, attribute):
        value = raw_sql_escape(self.regexp)

        if attribute.type == 'hostname':
            template = (
                '{{0}} IN ('
                '   SELECT server_id'
                '   FROM admin_server'
                '   WHERE hostname REGEXP {0}'
                ')'
                .format(value)
            )
        else:
            template = '{0} REGEXP ' + value

        return _condition_sql(attribute, template)

    def matches(self, server_obj, attr_name):
        value = str(server_obj[attr_name])
        return bool(self._regexp_obj.search(value))

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

        if attribute.type == 'hostname':
            raise FilterValueError('Hostnames cannot be compared.')

        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, attribute):
        return _condition_sql(attribute, '{{0}} {0} {1}'.format(
            self.comparator, value_to_sql(attribute, self.value)
        ))

    def matches(self, server_obj, attr_name):
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

        return op(server_obj[attr_name], self.value)

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

    def as_sql_expr(self, attribute):
        if not self.values:
            return '0 = 1'

        return _condition_sql(attribute, '{{0}} IN ({0})'.format(
            ', '.join(value_to_sql(attribute, v) for v in self.values)
        ))

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] in self.values

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

    def as_sql_expr(self, attribute):
        joiner = ' {0} '.format(type(self).__name__.upper())

        return '({0})'.format(joiner.join(
            v.as_sql_expr(attribute) for v in self.filters
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
    def matches(self, server_obj, attr_name):
        for filter in self.filters:
            if not filter.matches(server_obj, attr_name):
                return False
        return True


class Or(_AndOr):
    def matches(self, server_obj, attr_name):
        for filter in self.filters:
            if filter.matches(server_obj, attr_name):
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

        if attribute.type == 'hostname':
            raise FilterValueError('Hostnames cannot be compared.')

        self.a = typecast(attribute, self.a, force_single=True)
        self.b = typecast(attribute, self.b, force_single=True)

    def as_sql_expr(self, attribute):
        return _condition_sql(attribute, '{{0}} BETWEEN {0} AND {1}'.format(
            value_to_sql(attribute, self.a), value_to_sql(attribute, self.b)
        ))

    def matches(self, server_obj, attr_name):
        return self.a <= server_obj[attr_name] <= self.b

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

    def as_sql_expr(self, attribute):
        return 'NOT ({0})'.format(self.filter.as_sql_expr(attribute))

    def matches(self, server_obj, attr_name):
        return not self.filter.matches(server_obj, attr_name)

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
        self.value = unicode(self.value)

    def as_sql_expr(self, attribute):
        value = self.value.replace('_', '\\_').replace('%', '\\%%')
        value = raw_sql_escape(value + '%%')

        if attribute.type == 'hostname':
            template = (
                '{{0}} IN ('
                '   SELECT server_id'
                '   FROM admin_server'
                '   WHERE hostname LIKE {0}'
                ')'
                .format(value),
            )
        else:
            template = '{0} LIKE ' + value

        return _condition_sql(attribute, template)

    def matches(self, server_obj, attr_name):
        return unicode(server_obj[attr_name]).startswith(self.value)

    def as_code(self):
        return 'filters.Startswith({0!r})'.format(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj and isinstance(obj['value'], basestring):
            return cls(obj['value'])
        raise FilterValueError('Invalid object for Startswith')


class InsideNetwork(NetworkFilter):
    def __init__(self, *networks):
        try:
            self.networks = [ip_network(n) for n in networks]
        except ValueError as error:
            raise FilterValueError(str(error))

    def __repr__(self):
        return 'InsideNetwork({0})'.format(
            ', '.join(repr(n) for n in self.networks)
        )

    def __eq__(self, other):
        if isinstance(other, InsideNetwork):
            return all(
                n1 == n2 for n1, n2 in zip(self.networks, other.networks)
            )

        return False

    def __hash__(self):
        result = hash('InsideNetwork')
        for network in self.networks:
            result ^= hash(network)

        return result

    def as_sql_expr(self, attribute):
        return _condition_sql(attribute, '({0})'.format(
            ' OR '.join('{{0}} BETWEEN {0} AND {1}'.format(
                int(net.network_address), int(net.broadcast_address)
            ) for net in self.networks)
        ))

    def matches(self, server_obj, attr_name):
        return any(server_obj[attr_name] in n for n in self.networks)

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):

        if 'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj['networks'])

        raise FilterValueError('Invalid object for InsideNetwork')


class PrivateIP(NetworkFilter, NoArgFilter):
    blocks = (
        ip_network('10.0.0.0/8'),
        ip_network('172.16.0.0/12'),
        ip_network('192.168.0.0/16'),
    )

    def __init__(self):
        self.filt = InsideNetwork(*PrivateIP.blocks)

    def as_sql_expr(self, attribute):
        return self.filt.as_sql_expr(attribute)


class PublicIP(NetworkFilter, NoArgFilter):
    def __init__(self):
        self.filt = Not(InsideNetwork(*PrivateIP.blocks))

    def as_sql_expr(self, attribute):
        return self.filt.as_sql_expr(attribute)


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

    def as_sql_expr(self, attribute):
        return self.filter.as_sql_expr(attribute)

    def matches(self, server_obj, attr_name):

        value = server_obj.get(attr_name)
        if value is None:
            return True

        return self.filter.matches(server_obj, attr_name)

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

    def as_sql_expr(self, attribute):
        return 'NOT ' + _condition_sql(attribute, '{0} IS NOT NULL')

    def matches(self, server_obj, attr_name):
        return attr_name not in server_obj or len(server_obj[attr_name]) == 0

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

    if attribute.type == 'hostname':
        try:
            return str(Server.objects.get(hostname=value).server_id)
        except Server.DoesNotExist as error:
            raise FilterValueError(str(error))

    if attribute.type == 'number':
        return str(Decimal(value))

    # Those needs to be quoted, because they are stored as string on
    # the database.
    if attribute.type == 'boolean':
        return raw_sql_escape('1' if value else '0')
    if attribute.type == 'integer':
        return raw_sql_escape(str(int(value)))
    if attribute.type == 'ip':
        return raw_sql_escape(str(int(IPv4Address(value))))
    if attribute.type == 'ipv6':
        return raw_sql_escape(
            ''.join('{:02x}'.format(x) for x in IPv6Address(value).packed)
        )
    if attribute.type == 'datetime':
        return raw_sql_escape(str(
            int(time.mktime(dateutil.parser.parse(str(value)).timetuple()))
        ))
    return raw_sql_escape(value)


def _condition_sql(attribute, template):
    if attribute.special:
        field = attribute.special.field
        if field.startswith('_'):
            field = field[1:]

        return template.format(field)

    if attribute.reversed_attribute:
        attribute = attribute.reversed_attribute
        assert attribute.type == 'hostname'

        relation_column = 'sub.value'
        main_condition = template.format('sub.server_id')
    else:
        relation_column = 'sub.server_id'
        main_condition = template.format('sub.value')

    # We start with the condition for the attributes the server has on
    # its own.  Then, add the conditions for all possible relations.
    # They are going to be OR'ed together.
    relation_conditions = ['adms.server_id = ' + relation_column]

    for sa in ServertypeAttribute.objects.all():
        if sa.attribute == attribute and sa.related_via_attribute:
            assert sa.related_via_attribute.type == 'hostname'

            relation_conditions.append(
                'EXISTS ('
                '   SELECT 1'
                '   FROM {0} AS sub_rel'
                '   WHERE'
                '           sub_rel.server_id = adms.server_id'
                '       AND'
                "           sub_rel.attrib_id = '{1}'"
                '       AND'
                '           sub_rel.value = {2}'
                ')'
                .format(
                    ServerAttribute.get_model('hostname')._meta.db_table,
                    sa.related_via_attribute.pk,
                    relation_column,
                )
            )

    return (
        'EXISTS ('
        '   SELECT 1'
        '   FROM {0} AS sub'
        "   WHERE sub.attrib_id = '{1}' AND {2} AND ({3})"
        ')'
        .format(
            ServerAttribute.get_model(attribute.type)._meta.db_table,
            attribute.pk,
            main_condition,
            ' OR '.join(relation_conditions),
        )
    )


def raw_sql_escape(value):

    # escape_string just takes bytestrings, so convert unicode back and forth
    if isinstance(value, unicode):
        value = value.encode('utf-8')

    if "'" in value:
        raise FilterValueError('Single quote cannot be used')

    if value.endswith('\\'):
        raise FilterValueError('Escape character cannot be used in the end')

    value = value.replace('{', '{{').replace('}', '}}')

    return "'" + value.decode('utf-8') + "'"


def flatten(values):
    for value in values:
        if isinstance(value, (tuple, list, set)):
            for subvalue in flatten(value):
                yield subvalue
        else:
            yield value
