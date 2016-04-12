import re
import operator
import time
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_network

from serveradmin.dataset.base import lookups
from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import ServerObject

class BaseFilter(object):
    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

class NoArgFilter(BaseFilter):
    def __repr__(self):
        return u'{0}()'.format(type(self).__name__)

    def __eq__(self, other):
        return isinstance(other, type(self))

    def __hash__(self):
        return hash(type(self).__name__)

    def typecast(self, attribute):
        # We don't have values to typecast
        pass

    def as_sql_expr(self, builder, attribute, field):
        return self.filt.as_sql_expr(builder, attribute, field)

    def matches(self, server_obj, attr_name):
        return self.filt.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.{0}()'.format(type(self).__name__)

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
        return u'ExactMatch({0!r})'.format(self.value)

    def __eq__(self, other):
        if isinstance(other, ExactMatch):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(u'ExactMatch') ^ hash(self.value)

    def typecast(self, attribute):
        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, builder, attribute, field):

        value = value_to_sql(attribute, self.value)

        if attribute.type == 'hostname' or attribute.multi:
            return _exists_sql(attribute, 'value = ' + value)

        if attribute.type == 'boolean' and not self.value:
            return u"({0} = '0' OR {0} IS NULL)".format(field)

        return u'{0} = {1}'.format(field, value)

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] == self.value

    def as_code(self):
        return repr(self.value)

    @classmethod
    def from_obj(cls, obj):
        if u'value' in obj:
            return cls(obj[u'value'])

        raise ValueError('Invalid object for ExactMatch')

class Regexp(BaseFilter):
    def __init__(self, regexp):
        try:
            self._regexp_obj = re.compile(regexp)
        except re.error as e:
            raise ValueError(u'Invalid regexp: ' + unicode(e))

        self.regexp = regexp

    def __repr__(self):
        return u'Regexp({0!r})'.format(self.regexp)

    def __eq__(self, other):
        if isinstance(other, Regexp):
            return self.regexp == other.regexp
        return False

    def __hash__(self):
        return hash(u'Regexp') ^ hash(self.regexp)

    def typecast(self, attribute):
        # Regexp value is always string, no need to typecast
        pass

    def as_sql_expr(self, builder, attribute, field):

        sql_regexp = raw_sql_escape(self.regexp)

        if attribute.type == 'hostname':
            return _exists_sql(
                attribute,
                (
                    'value IN ('
                    '   SELECT server_id'
                    '   FROM admin_server'
                    '   WHERE hostname REGEXP {0}'
                    ')'
                ).format(sql_regexp),
            )

        if attribute.multi:
            return _exists_sql(attribute, 'value REGEXP ' + sql_regexp)

        if attribute.type == u'ip':
            return u'INET_NTOA({0}) REGEXP {1}'.format(field, sql_regexp)

        return u'{0} REGEXP {1}'.format(field, sql_regexp)

    def matches(self, server_obj, attr_name):
        value = str(server_obj[attr_name])
        return bool(self._regexp_obj.search(value))

    def as_code(self):
        return u'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if u'regexp' in obj and isinstance(obj[u'regexp'], basestring):
            return cls(obj[u'regexp'])
        raise ValueError(u'Invalid object for Regexp')

class Comparison(BaseFilter):
    def __init__(self, comparator, value):
        if comparator not in (u'<', u'>', u'<=', u'>='):
            raise ValueError(u'Invalid comparison operator: ' + comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return u'Comparison({0!r}, {1!r})'.format(self.comparator, self.value)

    def __eq__(self, other):
        if isinstance(other, Comparison):
            return (self.comparator == other.comparator and
                    self.value == other.value)
        return False

    def __hash__(self):
        return hash(u'Comparison') ^ hash(self.comparator) ^ hash(self.value)

    def typecast(self, attribute):

        if attribute.type == 'hostname':
            raise ValueError('Hostnames cannot be compared.')

        self.value = typecast(attribute, self.value, force_single=True)

    def as_sql_expr(self, builder, attribute, field):
        return u'{0} {1} {2}'.format(
                field,
                self.comparator,
                value_to_sql(attribute, self.value)
            )

    def matches(self, server_obj, attr_name):

        if self.comparator == '<':
            op = operator.lt
        elif self.comparator == '>':
            op = operator.gt
        elif operator.le == '<=':
            op = operator.le
        elif operator.gt == '>=':
            op = operator.gt
        else:
            raise ValueError('Operator doesn\'t exists')

        return op(server_obj[attr_name], self.value)

    def as_code(self):
        return u'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if u'comparator' in obj and u'value' in obj:
            return cls(obj[u'comparator'], obj[u'value'])
        raise ValueError(u'Invalid object for Comparison')

class Any(BaseFilter):
    def __init__(self, *values):
        self.values = set(flatten(values))

    def __repr__(self):
        return u'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def __eq__(self, other):
        if isinstance(other, Any):
            return self.values == other.values
        return False

    def __hash__(self):
        h = hash(u'Any')
        for val in self.values:
            h ^= hash(val)
        return h

    def typecast(self, attribute):
        self.values = set(
            typecast(attribute, x, force_single=True)
            for x in self.values
        )

    def as_sql_expr(self, builder, attribute, field):
        if not self.values:
            return u'0 = 1'

        values_csv = ', '.join(value_to_sql(attribute, v) for v in self.values)

        if attribute.type == 'hostname' or attribute.multi:
            return _exists_sql(attribute, 'value IN ({0})'.format(values_csv))

        return u'{0} IN ({1})'.format(field, values_csv)

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] in self.values

    def as_code(self):
        return u'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):
        if u'values' in obj and isinstance(obj[u'values'], list):
            return cls(*obj[u'values'])
        raise ValueError(u'Invalid object for Any')

class _AndOr(BaseFilter):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = u', '.join(repr(filt) for filt in self.filters)

        return u'{0}({1})'.format(type(self), args)

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

    def as_sql_expr(self, builder, attribute, field):

        joiner = u' {0} '.format(type(self).__name__.upper())

        return u'({0})'.format(joiner.join(
            filter.as_sql_expr(builder, attribute, field)
            for filter in self.filters
        ))

    def as_code(self):

        args = u', '.join(filt.as_code() for filt in self.filters)

        return u'filters.{0}({1})'.format(type(self), args)

    @classmethod
    def from_obj(cls, obj):

        if u'filters' in obj and isinstance(obj[u'filters'], list):
            if not obj['filters']:
                raise ValueError('Empty filters for And/Or')

            return cls(*[filter_from_obj(filter) for filter in obj[u'filters']])

        raise ValueError(u'Invalid object for {0}'.format(cls.__name__))

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
        return u'Between({0!r}, {1!r})'.format(self.a, self.b)

    def __eq__(self, other):
        if isinstance(other, Between):
            return self.a == other.a and self.b == other.b
        return False

    def __hash__(self):
        return hash(u'Between') ^ hash(self.a) ^ hash(self.b)

    def typecast(self, attribute):

        if attribute.type == 'hostname':
            raise ValueError('Hostnames cannot be compared.')

        self.a = typecast(attribute, self.a, force_single=True)
        self.b = typecast(attribute, self.b, force_single=True)

    def as_sql_expr(self, builder, attribute, field):

        a_prepared = value_to_sql(attribute, self.a)
        b_prepared = value_to_sql(attribute, self.b)

        return u'{0} BETWEEN {1} AND {2}'.format(field, a_prepared, b_prepared)

    def matches(self, server_obj, attr_name):
        return self.a <= server_obj[attr_name] <= self.b

    def as_code(self):
        return u'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):

        if u'a' in obj and u'b' in obj:
            return cls(obj[u'a'], obj[u'b'])

        raise ValueError(u'Invalid object for Between')

class Not(BaseFilter):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return u'Not({0!})'.format(self.filter)

    def __eq__(self, other):

        if isinstance(other, Not):
            return self.filter == other.filter

        return False

    def __hash__(self):
        return hash(u'Not') ^ hash(self.filter)

    def typecast(self, attribute):
       self.filter.typecast(attribute)

    def as_sql_expr(self, builder, attribute, field):

        return u'NOT ({0})'.format(
            self.filter.as_sql_expr(builder, attribute, field),
        )

    def matches(self, server_obj, attr_name):
        return not self.filter.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.Not({0})'.format(self.filter.as_code())

    @classmethod
    def from_obj(cls, obj):

        if u'filter' in obj:
            return cls(filter_from_obj(obj[u'filter']))

        raise ValueError(u'Invalid object for Not')

class Startswith(BaseFilter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return u'Startswith({0!})'.format(self.value)

    def __eq__(self, other):
        if isinstance(other, Startswith):
            return self.value == other.value

    def __hash__(self):
        return hash(u'Startswith') ^ hash(self.value)

    def typecast(self, attribute):
        self.value = unicode(self.value)

    def as_sql_expr(self, builder, attribute, field):

        value = self.value.replace('_', '\\_').replace(u'%', u'\\%%')
        value = raw_sql_escape(value + u'%%')

        if attribute.type == 'hostname':
            return _exists_sql(
                attribute,
                (
                    'value IN ('
                    '   SELECT server_id'
                    '   FROM admin_server'
                    '   WHERE hostname LIKE {0}'
                    ')'
                ).format(value),
            )

        if attribute.type == u'ip':
            return u'INET_NTOA({0}) LIKE {1}'.format(field, value)

        if attribute.type == 'string':
            return u'{0} LIKE {1}'.format(field, value)

        if attribute.type == 'integer':
            try:
                return u"{0} LIKE '{1}%'".format(int(self.value))
            except ValueError:
                return u'0 = 1'

        return u'0 = 1'

    def matches(self, server_obj, attr_name):
        return unicode(server_obj[attr_name]).startswith(self.value)

    def as_code(self):
        return u'filters.Startswith({0!r})'.format(self.value)

    @classmethod
    def from_obj(cls, obj):
        if u'value' in obj and isinstance(obj[u'value'], basestring):
            return cls(obj[u'value'])
        raise ValueError(u'Invalid object for Startswith')

class InsideNetwork(NetworkFilter):
    def __init__(self, *networks):
        self.networks = [ip_network(n) for n in networks]

    def __repr__(self):
        return u'InsideNetwork({0})'.format(
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

    def as_sql_expr(self, builder, attribute, field):

        betweens = ['{0} BETWEEN {1} AND {2}'.format(
            field,
            int(net.network_address),
            int(net.broadcast_address),
        ) for net in self.networks]

        return u'({0})'.format(u' OR '.join(betweens))

    def matches(self, server_obj, attr_name):

        return any(
            net.min_ip <= server_obj[attr_name] <= net.max_ip
            for net in self.networks
        )

    def as_code(self):
        return u'filters.' + repr(self)

    @classmethod
    def from_obj(cls, obj):

        if u'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj[u'networks'])

        raise ValueError(u'Invalid object for InsideNetwork')

class PrivateIP(NetworkFilter, NoArgFilter):

    blocks = (
        ip_network('10.0.0.0/8'),
        ip_network('172.16.0.0/12'),
        ip_network('192.168.0.0/16'),
    )

    def __init__(self):
        self.filt = InsideNetwork(*PrivateIP.blocks)

class PublicIP(NetworkFilter, NoArgFilter):

    def __init__(self):
        self.filt = Not(InsideNetwork(*PrivateIP.blocks))

class Optional(OptionalFilter):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return u'Optional({0!r})'.format(self.filter)

    def __eq__(self, other):
        if isinstance(other, Optional):
            return self.filter == other.filter
        return False

    def __hash__(self):
        return hash(u'Optional') ^ hash(self.filter)

    def typecast(self, attribute):
        self.filter.typecast(attribute)

    def as_sql_expr(self, builder, attribute, field):
        return u'({0} IS NULL OR {1})'.format(
            field,
            self.filter.as_sql_expr(builder, attribute, field),
        )

    def matches(self, server_obj, attr_name):

        value = server_obj.get(attr_name)
        if value is None:
            return True

        return self.filter.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.Optional({0})'.format(self.filter.as_code())

    @classmethod
    def from_obj(cls, obj):

        if u'filter' in obj:
            return cls(filter_from_obj(obj[u'filter']))

        raise ValueError(u'Invalid object for Optional')

class Empty(OptionalFilter):
    def __repr__(self):
        return u'Empty()'

    def __eq__(self, other):
        return isinstance(other, Empty)

    def __hash__(self):
        return hash('Empty')

    def typecast(self, attribute):
        pass

    def as_sql_expr(self, builder, attribute, field):

        if attribute.type == 'hostname' or attribute.multi:
            return 'NOT {0}'.format(_exists_sql(attribute))

        return u'{0} IS NULL'.format(field)

    def matches(self, server_obj, attr_name):
        return attr_name not in server_obj or len(server_obj[attr_name]) == 0

    def as_code(self):
        return u'filters.Empty()'

    @classmethod
    def from_obj(cls, obj):
        return cls()

def _prepare_filter(filter):
    return filter if isinstance(filter, BaseFilter) else ExactMatch(filter)

def filter_from_obj(obj):

    if not (
            isinstance(obj, dict)
        and
            u'name' in obj
        and
            isinstance(obj[u'name'], basestring)
    ):
        raise ValueError(u'Invalid filter object')

    try:
        return filter_classes[obj[u'name']].from_obj(obj)
    except KeyError:
        raise ValueError(u'No such filter: {0}'.format(obj[u'name']))

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
    if attribute.type == u'boolean':
        value = 1 if value else 0
    elif attribute.type == u'ip':
        if not isinstance(value, IPv4Address):
            value = IPv4Address(value)
        value = int(value)
    elif attribute.type == u'ipv6':
        if not isinstance(value, IPv6Address):
            value = IPv6Address(value)
        value = ''.join('{:02x}'.format(x) for x in value.packed)
    elif attribute.type == u'datetime':
        if isinstance(value, datetime):
            value = int(time.mktime(value.timetuple()))
    elif attribute.type == 'hostname':
        try:
            value = ServerObject.objects.get(hostname=value).server_id
        except ServerObject.DoesNotExist:
            raise ValueError('No server with hostname "{0}"'.format(value))

    # Validations of special attributes
    if attribute.pk == u'servertype':
        if value not in lookups.servertypes:
            raise ValueError(u'Invalid servertype: ' + value)
    if attribute.pk == u'segment':
        if value not in lookups.segments:
            raise ValueError(u'Invalid segment: ' + value)
    if attribute.pk == u'project':
        if value not in lookups.projects:
            raise ValueError(u'Invalid project: ' + value)

    return _sql_escape(value)

def _exists_sql(attribute, cond=None):

    if attribute.type == 'hostname':
        table = 'server_hostname_attrib'
    else:
        table = 'attrib_values'

    if cond:
        and_cond = ' AND sub{0}.{1}'.format(attribute.attrib_id, cond)
    else:
        and_cond = ''

    return (
        'EXISTS ('
        '   SELECT 1'
        '   FROM {0} AS sub{1}'
        '   WHERE'
        '           sub{1}.server_id = adms.server_id'
        '       AND'
        "           sub{1}.attrib_id = '{1}'"
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
        return u'1' if value else u'0'

    if isinstance(value, datetime):
        return unicode(time.mktime(value.timetuple()))

    raise ValueError(
        u'Value of type {0} can not be used in SQL'.format(value)
    )


def raw_sql_escape(value):

    # escape_string just takes bytestrings, so convert unicode back and forth
    if isinstance(value, unicode):
        value = value.encode('utf-8')

    if "'" in value:
        raise ValueError(u'Single quote cannot be used')

    if value.endswith('\\'):
        raise ValueError(u'Escape character cannot be used in the end')

    return "'" + value.decode('utf-8') + "'"


def flatten(values):
    for value in values:
        if isinstance(value, (tuple, list, set)):
            for subvalue in flatten(value):
                yield subvalue
        else:
            yield value

