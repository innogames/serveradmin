from adminapi.utils import IP
from serveradmin.dataset.base import lookups

_filter_classes = {}

class ExactMatch(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'ExactMatch({0!r})'.format(self.value)

    def as_sql_expr(self, attr_name, field):
        return '{0} = {1}'.format(field, _prepare_value(attr_name, self.value))

    @classmethod
    def from_obj(cls, obj):
        pass
_filter_classes['exactmatch'] = ExactMatch

class Regexp(object):
    def __init__(self, regexp):
        self.regexp = regexp

    def __repr__(self):
        return 'Regexp({0!r})'.format(self.regexp)

    def as_sql_expr(self, attr_name, field):
        if lookups.attr_names[attr_name].type == 'ip':
            return 'NTOA({0}) REGEXP {1}'.format(field, _sql_escape(self.regexp))
        else:
            return '{0} REGEXP {1}'.format(field, _sql_escape(self.regexp))

    @classmethod
    def from_obj(cls, obj):
        pass
_filter_classes['regexp'] = Regexp

class Comparism(object):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise ValueError('Invalid comparism operator: ' + self.comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparism({0!r}, {1!r})'.format(self.comparator, self.value)

    def as_sql_expr(self, attr_name, field):
        return '{0} {1} {2}'.format(field, self.comparator,
                _prepare_value(attr_name, self.value))

    @classmethod
    def from_obj(cls, obj):
        pass
_filter_classes['comparism'] = Comparism

class Any(object):
    def __init__(self, *values):
        self.values = values

    def __repr__(self):
        return 'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def as_sql_expr(self, attr_name, field):
        if not self.values:
            return '0=1'
        else:
            return 'IN({0})'.format(', '.join(_prepare_value(attr_name, value)
                    for value in self.values))
    
    @classmethod
    def from_obj(cls, obj):
        pass
_filter_classes['any'] = Any

class _AndOr(object):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = ', '.join(repr(filter) for filter in self.filters)
        return '{0}({1})'.format(self.name.capitalize(), args)

    def as_sql_expr(self, field):
        joiner = ' {0} '.format(self.name.upper())
        return '({0})'.format(joiner.join([filter.as_sql_expr(field)
                for filter in self.filters]))

    @classmethod
    def from_obj(obj):
        pass

class And(_AndOr):
    name = 'and'
_filter_classes['and'] = And

class Or(_AndOr):
    name = 'or'
_filter_classes['or'] = Or

class Between(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Between({0!r}, {1!r})'.format(self.a, self.b)

    def as_sql_expr(self, attr_name, field):
        a_prepared = _prepare_value(attr_name, self.a)
        b_prepared = _prepare_value(attr_name, self.b)
        return '{0} BETWEEN {1} AND {2}'.format(field, a_prepared, b_prepared)

    @classmethod
    def from_obj(obj):
        pass
_filter_classes['between'] = Between

class Optional(object):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Optional({0!r})'.format(self.filter)

    def as_sql_expr(self, field):
        return self.filter.as_sql_expr(field)

    @classmethod
    def from_obj(obj):
        pass
_filter_classes['optional'] = Optional

def _prepare_filter(filter):
    return (ExactMatch(filter) if isinstance(filter, (int, basestring, bool))
            else filter)

def _prepare_value(attr_name, value):
    if lookups.attr_names[attr_name].type == 'ip':
        if not isinstance(value, IP):
            value = IP(value)
        value = value.as_int()
    # XXX: Dirty hack for the old database structure
    if attr_name == 'servertype':
        value = lookups.stype_names[value].pk

    return _sql_escape(value)

def _sql_escape(value):
    if isinstance(value, basestring):
        # FIXME: Prevent SQL Injections using real database escaping
        return "'{0}'".format(value.replace('\\', '\\\\'))
    elif isinstance(value, (int, long, float)):
        return str(value)
    elif isinstance(value, bool):
        return '1' if value else '0'
    else:
        raise ValueError('Value of type {0} can not be used in SQL'.format(
                type(value)))

def filter_from_obj(obj):
    pass
    
