import re
import operator
import time
from datetime import datetime

from django.db import connection, DatabaseError

from adminapi.utils import IP, IPv6, Network, PRIVATE_IP_BLOCKS, PUBLIC_IP_BLOCKS
from serveradmin.dataset.base import lookups
from serveradmin.dataset.exceptions import DatasetError
from serveradmin.dataset.typecast import typecast

filter_classes = {}
class BaseFilter(object):
    pass

class Filter(BaseFilter):
    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

class ExactMatch(Filter):
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

    def as_sql_expr(self, builder, attr_obj, field):
        return u'{0} = {1}'.format(field, _prepare_value(attr_obj, self.value))

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] == self.value

    def as_code(self):
        return repr(self.value)

    def typecast(self, attr_name):
        self.value = typecast(attr_name, self.value, force_single=True)

    @classmethod
    def from_obj(cls, obj):
        if u'value' in obj:
            return cls(obj[u'value'])
        raise ValueError('Invalid object for ExactMatch')
filter_classes[u'exactmatch'] = ExactMatch

class Regexp(Filter):
    def __init__(self, regexp):
        try:
            self._regexp_obj = re.compile(regexp)
            c = connection.cursor()
            c.execute("SELECT '' REGEXP {0}".format(_sql_escape(regexp)))
            c.close()
        except re.error as e:
            raise ValueError(u'Invalid regexp: ' + unicode(e))
        except DatabaseError as e:
            raise ValueError(u'Invalid regexp: ' + e[1])
        
        self.regexp = regexp

    def __repr__(self):
        return u'Regexp({0!r})'.format(self.regexp)

    def __eq__(self, other):
        if isinstance(other, Regexp):
            return self.regexp == other.regexp
        return False

    def __hash__(self):
        return hash(u'Regexp') ^ hash(self.regexp)

    def as_sql_expr(self, builder, attr_obj, field):
        # XXX Dirty hack for servertype regexp checking
        if attr_obj.name == u'servertype':
            stype_ids = []
            for stype in lookups.stype_ids.itervalues():
                if self._regexp_obj.search(stype.name):
                    stype_ids.append(unicode(stype.pk))
            if stype_ids:
                return u'{0} IN({1})'.format(field, ', '.join(stype_ids))
            else:
                return u'0=1'
        elif attr_obj.type == u'ip':
            return u'INET_NTOA({0}) REGEXP {1}'.format(field, _sql_escape(self.regexp))
        else:
            return u'{0} REGEXP {1}'.format(field, _sql_escape(self.regexp))

    def matches(self, server_obj, attr_name):
        value = server_obj[attr_name]
        if lookups.attr_names[attr_name].type == u'ip':
            value = value.as_ip()
        else:
            value = str(value)
        
        return bool(self._regexp_obj.search(value))

    def as_code(self):
        return u'filters.' + repr(self)

    def typecast(self, attr_name):
        # Regexp value is always string, no need to typecast
        pass

    @classmethod
    def from_obj(cls, obj):
        if u'regexp' in obj and isinstance(obj[u'regexp'], basestring):
            return cls(obj[u'regexp'])
        raise ValueError(u'Invalid object for Regexp')
filter_classes[u'regexp'] = Regexp

class Comparison(Filter):
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

    def as_sql_expr(self, builder, attr_obj, field):
        return u'{0} {1} {2}'.format(field, self.comparator,
                _prepare_value(attr_obj, self.value))

    def matches(self, server_obj, attr_name):
        op = {
            u'<': operator.lt,
            u'>': operator.gt,
            u'<=': operator.le,
            u'>=': operator.gt
        }[self.comparator]
        return op(server_obj[attr_name], self.value)

    def as_code(self):
        return u'filters.' + repr(self)

    def typecast(self, attr_name):
        self.value = typecast(attr_name, self.value, force_single=True)

    @classmethod
    def from_obj(cls, obj):
        if u'comparator' in obj and u'value' in obj:
            return cls(obj[u'comparator'], obj[u'value'])
        raise ValueError(u'Invalid object for Comparism')
filter_classes[u'comparison'] = Comparison

class Any(Filter):
    def __init__(self, *values):
        self.values = set(values)

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

    def as_sql_expr(self, builder, attr_obj, field):
        if not self.values:
            return u'0=1'
        else:
            prepared_values = u', '.join(_prepare_value(attr_obj, value)
                    for value in self.values)
            return u'{0} IN({1})'.format(field, prepared_values)

    def matches(self, server_obj, attr_name):
        return server_obj[attr_name] in self.values

    def as_code(self):
        return u'filters.' + repr(self)

    def typecast(self, attr_name):
        self.values = set(typecast(attr_name, x, force_single=True)
                          for x in self.values)

    @classmethod
    def from_obj(cls, obj):
        if u'values' in obj and isinstance(obj[u'values'], list):
            return cls(*obj[u'values'])
        raise ValueError(u'Invalid object for Any')
filter_classes[u'any'] = Any

class _AndOr(Filter):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = u', '.join(repr(filt) for filt in self.filters)
        return u'{0}({1})'.format(self.name.capitalize(), args)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.filters == other.filters
        return False

    def __hash__(self):
        h = hash(self.name)
        for val in self.filters:
            h ^= hash(val)
        return h

    def as_sql_expr(self, builder, attr_obj, field):
        joiner = u' {0} '.format(self.name.upper())
        return u'({0})'.format(joiner.join([filter.as_sql_expr(builder, attr_obj, field)
                for filter in self.filters]))
    
    def as_code(self):
        args = u', '.join(filt.as_code() for filt in self.filters)
        return u'filters.{0}({1})'.format(self.name.capitalize(), args)

    def typecast(self, attr_name):
        for filt in self.filters:
            filt.typecast(attr_name)

    @classmethod
    def from_obj(cls, obj):
        if u'filters' in obj and isinstance(obj[u'filters'], list):
            return cls(*[filter_from_obj(filter) for filter in obj[u'filters']])
        raise ValueError(u'Invalid object for {0}'.format(
                cls.__name__.capitalize()))

class And(_AndOr):
    name = u'and'

    def matches(self, server_obj, attr_name):
        for filter in self.filters:
            if not filter.matches(server_obj, attr_name):
                return False
        return True
filter_classes[u'and'] = And

class Or(_AndOr):
    name = u'or'
    
    def matches(self, server_obj, attr_name):
        for filter in self.filters:
            if filter.matches(server_obj, attr_name):
                return True
        return False
filter_classes[u'or'] = Or

class Between(Filter):
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

    def as_sql_expr(self, builder, attr_obj, field):
        a_prepared = _prepare_value(attr_obj, self.a)
        b_prepared = _prepare_value(attr_obj, self.b)
        return u'{0} BETWEEN {1} AND {2}'.format(field, a_prepared, b_prepared)

    def matches(self, server_obj, attr_name):
        return self.a <= server_obj[attr_name] <= self.b

    def as_code(self):
        return u'filters.' + repr(self)

    def typecast(self, attr_name):
        self.a = typecast(attr_name, self.a, force_single=True)
        self.b = typecast(attr_name, self.b, force_single=True)

    @classmethod
    def from_obj(cls, obj):
        if u'a' in obj and u'b' in obj:
            return cls(obj[u'a'], obj[u'b'])
        raise ValueError(u'Invalid object for Between')
filter_classes[u'between'] = Between

class Not(Filter):
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

    def as_sql_expr(self, builder, attr_obj, field):
        if attr_obj.multi:
            uid = builder.get_uid()
            cond = self.filter.as_sql_expr(builder, attr_obj,
                    'nav{0}.value'.format(uid))
            subquery = ('SELECT id FROM attrib_values AS nav{0} '
                        'WHERE {1} AND nav{0}.server_id = adms.server_id').format(
                                uid, cond)
            return 'NOT EXISTS ({0})'.format(subquery)
        else:
            if isinstance(self.filter, ExactMatch):
                return u'{0} != {1}'.format(field, _prepare_value(attr_obj,
                        self.filter.value))
            else:
                return u'NOT {0}'.format(self.filter.as_sql_expr(builder,
                        attr_obj, field))

    def matches(self, server_obj, attr_name):
        return not self.filter.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.Not({0})'.format(self.filter.as_code())

    def typecast(self, attr_name):
       self.filter.typecast(attr_name)

    @classmethod
    def from_obj(cls, obj):
        if u'filter' in obj:
            return cls(filter_from_obj(obj[u'filter']))
        raise ValueError(u'Invalid object for Not')
filter_classes[u'not'] = Not

class Startswith(Filter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return u'Startswith({0!})'.format(self.value)
    
    def __eq__(self, other):
        if isinstance(other, Startswith):
            return self.value == other.value

    def __hash__(self):
        return hash(u'Startswith') ^ hash(self.value)

    def as_sql_expr(self, builder, attr_obj, field):
        # XXX Dirty hack for servertype checking
        if attr_obj.name == u'servertype':
            stype_ids = []
            for stype in lookups.stype_ids.itervalues():
                if stype.name.startswith(self.value):
                    stype_ids.append(unicode(stype.pk))
            if stype_ids:
                return u'{0} IN({1})'.format(field, ', '.join(stype_ids))
            else:
                return u'0=1'
        elif attr_obj.type == u'ip':
            return u'INET_NTOA({0}) LIKE {1}'.format(field, _sql_escape(value +
                '%%'))
        elif attr_obj.type == 'string':
            value = self.value.replace('_', '\\_').replace(u'%', u'\\%%')
            return u'{0} LIKE {1}'.format(field, _sql_escape(value + u'%%'))
        elif attr_obj.type == 'integer':
            try:
                return u"{0} LIKE '{1}%'".format(int(self.value))
            except ValueError:
                return u'0=1'
        else:
            return u'0=1'

    def matches(self, server_obj, attr_name):
        return unicode(server_obj[attr_name]).startswith(self.value)

    def as_code(self):
        return u'filters.Startswith({0!r})'.format(self.value)

    def typecast(self, attr_name):
        self.value = typecast(attr_name, self.value, force_single=True)
    
    @classmethod
    def from_obj(cls, obj):
        if u'value' in obj and isinstance(obj[u'value'], basestring):
            return cls(obj[u'value'])
        raise ValueError(u'Invalid object for Startswith')
filter_classes[u'startswith'] = Startswith

class InsideNetwork(Filter):
    def __init__(self, *networks):
        # Avoid cyclic imports. Using other components inside dataset
        # is really a problem. TODO: Think about solutions
        from serveradmin.iprange.models import IPRange
        self.networks = []
        self.iprange_mapping = {}
        for network in networks:
            if not isinstance(network, Network):
                if isinstance(network, basestring) and '/' not in network:
                    try:
                        iprange = IPRange.objects.get(pk=network)
                        network_obj = Network(iprange.min, iprange.max)
                        self.iprange_mapping[network_obj] = network
                        network = network_obj
                    except IPRange.DoesNotExist:
                        raise DatasetError('No such IP range: ' + network)
                else:
                    network = Network(network)
            self.networks.append(network)

    def __repr__(self):
        args = []
        for network in self.networks:
            try:
                args.append(repr(self.iprange_mapping[network]))
            except KeyError:
                args.append(repr(network))
        return u'InsideNetwork({0})'.format(u', '.join(args))

    def __eq__(self, other):
        if isinstance(other, InsideNetwork):
            return all(
                    n1 == n2 for n1, n2 in zip(self.networks, other.networks))
        return False

    def __hash__(self):
        h = hash('InsideNetwork')
        for network in self.networks:
            h ^= hash(network)
        return h

    def as_sql_expr(self, builder, attr_obj, field):
        betweens = [
            u'{0} BETWEEN {1} AND {2}'.format(
            field, net.min_ip.as_int(), net.max_ip.as_int())
            for net in self.networks]

        return u'({0})'.format(u' OR '.join(betweens))

    def matches(self, server_obj, attr_name):
        return any(
            net.min_ip <= server_obj[attr_name] <= net.max_ip
            for net in self.networks)

    def as_code(self):
        return u'filters.' + repr(self)

    def typecast(self, attr_name):
        # Typecast was already done in __init__
        pass

    @classmethod
    def from_obj(cls, obj):
        if u'networks' in obj:
            return cls(*obj[u'networks'])
        raise ValueError(u'Invalid object for InsideNetwork')
filter_classes[u'insidenetwork'] = InsideNetwork

class _PrivatePublicIP(Filter):
    def __init__(self):
        self.filt = InsideNetwork(*self.blocks)
    
    def __repr__(self):
        return u'{0}()'.format(self.__class__.__name__)

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return hash(self.__class__.__name__)

    def as_sql_expr(self, builder, attr_obj, field):
        return self.filt.as_sql_expr(builder, attr_obj, field)

    def matches(self, server_obj, attr_name):
        return self.filt.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.{0}()'.format(self.__class__.__name__)

    def typecast(self, attr_name):
        # We don't have values to typecast
        pass
    
    @classmethod
    def from_obj(cls, obj):
        return cls()

class PrivateIP(_PrivatePublicIP):
    blocks = PRIVATE_IP_BLOCKS
filter_classes['privateip'] = PrivateIP

class PublicIP(_PrivatePublicIP):
    blocks = PUBLIC_IP_BLOCKS
filter_classes['publicip'] = PublicIP

class OptionalFilter(BaseFilter):
    pass

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

    def as_sql_expr(self, builder, attr_obj, field):
        return u'({0} IS NULL OR {1})'.format(field, self.filter.as_sql_expr(
                builder, attr_obj, field))

    def matches(self, server_obj, attr_name):
        value = server_obj.get(attr_name)
        if value is None:
            return True
        return self.filter.matches(server_obj, attr_name)

    def as_code(self):
        return u'filters.Optional({0})'.format(self.filter.as_code())

    def typecast(self, attr_name):
        self.filter.typecast(attr_name)

    @classmethod
    def from_obj(cls, obj):
        if u'filter' in obj:
            return cls(filter_from_obj(obj[u'filter']))
        raise ValueError(u'Invalid object for Optional')
filter_classes[u'optional'] = Optional

class Empty(OptionalFilter):
    def __repr__(self):
        return u'Empty()'

    def __eq__(self, other):
        return isinstance(other, Empty)

    def __hash__(self):
        return hash('Empty')
    
    def as_sql_expr(self, builder, attr_obj, field):
        return u'{0} IS NULL'.format(field)

    def matches(self, server_obj, attr_name):
        return attr_name not in server_obj or len(server_obj[attr_name]) == 0

    def as_code(self):
        return u'filters.Empty()'

    def typecast(self, attr_name):
        pass
    
    @classmethod
    def from_obj(cls, obj):
        return cls()
filter_classes[u'empty'] = Empty


def _prepare_filter(filter):
    return filter if isinstance(filter, BaseFilter) else ExactMatch(filter)

def _prepare_value(attr_obj, value):
    if attr_obj.type == u'ip':
        if not isinstance(value, IP):
            value = IP(value)
        value = value.as_int()
    elif attr_obj.type == u'ipv6':
        if not isinstance(value, IPv6):
            value = IPv6(value)
        value = value.as_hex()
    # XXX: Dirty hack for the old database structure
    if attr_obj.name == u'servertype':
        try:
            value = lookups.stype_names[value].pk
        except KeyError:
            raise ValueError(u'Invalid servertype: ' + value)

    return _sql_escape(value)

def _sql_escape(value):
    if isinstance(value, basestring):
        return u"'{0}'".format(value.replace("'", "\\'"))
    elif isinstance(value, (int, long, float)):
        return unicode(value)
    elif isinstance(value, bool):
        return u'1' if value else u'0'
    elif isinstance(value, datetime):
        return unicode(time.mktime(value.timetuple()))
    else:
        raise ValueError(u'Value of type {0} can not be used in SQL'.format(
                value))

def filter_from_obj(obj):
    if not (isinstance(obj, dict) and u'name' in obj and
            isinstance(obj[u'name'], basestring)):
        raise ValueError(u'Invalid filter object')
    try:
        if obj[u'name'] == 'comparism':
            obj[u'name'] = 'comparison' # Backward compatibility
        return filter_classes[obj[u'name']].from_obj(obj)
    except KeyError:
        raise ValueError(u'No such filter: {0}').format(obj[u'name'])

