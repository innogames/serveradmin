import re
import operator
import time
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_network

from serveradmin.dataset.base import lookups, DatasetError
from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import ServerObject


class FilterValueError(DatasetError):
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
            raise ValueError('Only IP addresses can be used by this filter.')


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
        value = value_to_sql(attribute, self.value)

        if attribute.special:
            return '{0} = {1}'.format(attribute.special.field, value)

        if attribute.type == 'boolean' and not self.value:
            return 'NOT {0}'.format(_exists_sql(attribute, "value = '1'"))

        return _exists_sql(attribute, 'value = ' + value)

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] == self.value

    def as_code(self):
        return repr(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise ValueError('Invalid object for ExactMatch')


class Regexp(BaseFilter):
    def __init__(self, regexp):
        try:
            self._regexp_obj = re.compile(regexp)
        except re.error as e:
            raise ValueError('Invalid regexp: ' + unicode(e))

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

        if attribute.special:
            return '{0} REGEXP {1}'.format(attribute.special.field, value)

        if attribute.type == 'hostname':
            return _exists_sql(
                attribute,
                'value IN ('
                '   SELECT server_id'
                '   FROM admin_server'
                '   WHERE hostname REGEXP {0}'
                ')'
                .format(value),
            )

        return _exists_sql(attribute, 'value REGEXP {0}'.format(value))

    def matches(self, server_obj, attr_name):
        value = str(server_obj[attr_name])
        return bool(self._regexp_obj.search(value))

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'regexp' in obj and isinstance(obj['regexp'], basestring):
            return cls(obj['regexp'])
        raise ValueError('Invalid object for Regexp')


class Comparison(BaseFilter):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise ValueError('Invalid comparison operator: ' + comparator)
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
            raise ValueError('Hostnames cannot be compared.')

        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, attribute):
        value = value_to_sql(attribute, self.value)

        if attribute.special:
            return '{0} {1} {2}'.format(
                attribute.special.field, self.comparator, value
            )

        return _exists_sql(attribute, 'value {0} {1}'.format(
            self.operator, value
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
            raise ValueError("Operator doesn't exists")

        return op(server_obj[attr_name], self.value)

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'comparator' in obj and 'value' in obj:
            return cls(obj['comparator'], obj['value'])
        raise ValueError('Invalid object for Comparison')


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

        values_csv = ', '.join(value_to_sql(attribute, v) for v in self.values)

        if attribute.special:
            return '{0} IN ({1})'.format(attribute.special.field, values_csv)

        return _exists_sql(attribute, 'value IN ({0})'.format(values_csv))

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] in self.values

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'values' in obj and isinstance(obj['values'], list):
            return cls(*obj['values'])
        raise ValueError('Invalid object for Any')


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
                raise ValueError('Empty filters for And/Or')

            return cls(*[filter_from_obj(filter) for filter in obj['filters']])

        raise ValueError('Invalid object for {0}'.format(cls.__name__))


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
            raise ValueError('Hostnames cannot be compared.')

        self.a = typecast(attribute, self.a, force_single=True)
        self.b = typecast(attribute, self.b, force_single=True)

    def as_sql_expr(self, attribute):
        a_prepared = value_to_sql(attribute, self.a)
        b_prepared = value_to_sql(attribute, self.b)

        if attribute.special:
            return '{0} BETWEEN {1} AND {2}'.format(
                attribute.special.field, a_prepared, b_prepared
            )

        return _exists_sql(attribute, 'value BETWEEN {0} AND {1}'.format(
            a_prepared, b_prepared
        ))

    def matches(self, server_obj, attr_name):
        return self.a <= server_obj[attr_name] <= self.b

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if 'a' in obj and 'b' in obj:
            return cls(obj['a'], obj['b'])

        raise ValueError('Invalid object for Between')


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

        raise ValueError('Invalid object for Not')


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

        if attribute.special:
            return '{0} LIKE {1}'.format(attribute.special.field, value)

        if attribute.type == 'hostname':
            return _exists_sql(
                attribute,
                'value IN ('
                '   SELECT server_id'
                '   FROM admin_server'
                '   WHERE hostname LIKE {0}'
                ')'
                .format(value),
            )

        return _exists_sql(attribute, 'value LIKE {0}'.format(value))

    def matches(self, server_obj, attr_name):
        return unicode(server_obj[attr_name]).startswith(self.value)

    def as_code(self):
        return 'filters.Startswith({0!r})'.format(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj and isinstance(obj['value'], basestring):
            return cls(obj['value'])
        raise ValueError('Invalid object for Startswith')


class InsideNetwork(NetworkFilter):
    def __init__(self, *networks):
        self.networks = [ip_network(n) for n in networks]

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
        template = '({0})'.format(
            ' OR '.join('{{0}} BETWEEN {0} AND {1}'.format(
                int(net.network_address), int(net.broadcast_address)
            ) for net in self.networks)
        )

        if attribute.special:
            return template.format(attribute.special.field)

        return _exists_sql(attribute, template)

    def matches(self, server_obj, attr_name):
        return any(server_obj[attr_name] in n for n in self.networks)

    def as_code(self):
        return 'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):

        if 'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj['networks'])

        raise ValueError('Invalid object for InsideNetwork')


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

        raise ValueError('Invalid object for Optional')


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
        if attribute.special:
            return '{0} IS NULL'.format(attribute.special.field)
        return 'NOT {0}'.format(_exists_sql(attribute))

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
        raise ValueError('Invalid filter object')

    try:
        return filter_classes[obj['name']].from_obj(obj)
    except KeyError:
        raise ValueError('No such filter: {0}'.format(obj['name']))


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

    # Casts by type
    if attribute.type == 'boolean':
        value = 1 if value else 0
    elif attribute.type == 'ip':
        if not isinstance(value, IPv4Address):
            value = IPv4Address(value)
        value = int(value)
    elif attribute.type == 'ipv6':
        if not isinstance(value, IPv6Address):
            value = IPv6Address(value)
        value = ''.join('{:02x}'.format(x) for x in value.packed)
    elif attribute.type == 'datetime':
        if isinstance(value, datetime):
            value = int(time.mktime(value.timetuple()))
    elif attribute.type == 'hostname':
        try:
            value = ServerObject.objects.get(hostname=value).server_id
        except ServerObject.DoesNotExist as error:
            raise FilterValueError(str(error))

    # Validations of special attributes
    if attribute.pk == 'servertype':
        if value not in lookups.servertypes:
            raise FilterValueError('Invalid servertype: ' + value)
    if attribute.pk == 'segment':
        if value not in lookups.segments:
            raise FilterValueError('Invalid segment: ' + value)
    if attribute.pk == 'project':
        if value not in lookups.projects:
            raise FilterValueError('Invalid project: ' + value)

    return _sql_escape(value)


def _exists_sql(attribute, cond=None):
    if attribute.type == 'hostname':
        table = 'server_hostname_attrib'
    else:
        table = 'attrib_values'

    if cond:
        and_cond = ' AND {0}'.format(cond)
    else:
        and_cond = ''

    return (
        'EXISTS ('
        '   SELECT 1'
        '   FROM {0} AS sub'
        '   WHERE'
        '           sub.server_id = adms.server_id'
        '       AND'
        "           sub.attrib_id = '{1}'"
        '       {2}'
        ')'
    ).format(
        table,
        attribute.attrib_id,
        and_cond,
    )


def _sql_escape(value):
    if isinstance(value, basestring):
        return raw_sql_escape(value)

    if isinstance(value, (int, long, float)):
        return unicode(value)

    if isinstance(value, bool):
        return '1' if value else '0'

    if isinstance(value, datetime):
        return unicode(time.mktime(value.timetuple()))

    raise ValueError(
        'Value of type {0} can not be used in SQL'.format(value)
    )


def raw_sql_escape(value):

    # escape_string just takes bytestrings, so convert unicode back and forth
    if isinstance(value, unicode):
        value = value.encode('utf-8')

    if "'" in value:
        raise FilterValueError('Single quote cannot be used')

    if value.endswith('\\'):
        raise FilterValueError('Escape character cannot be used in the end')

    return "'" + value.decode('utf-8') + "'"


def flatten(values):
    for value in values:
        if isinstance(value, (tuple, list, set)):
            for subvalue in flatten(value):
                yield subvalue
        else:
            yield value
