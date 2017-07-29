from re import compile as re_compile, error as re_error

from adminapi.base import QueryError


class FilterValueError(QueryError, ValueError):
    pass


class BaseFilter(object):
    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)


class ExactMatch(BaseFilter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'ExactMatch({0!r})'.format(self.value)

    def serialize(self):
        return {'name': 'exactmatch', 'value': self.value}

    def matches(self, value):
        return value == self.value

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise FilterValueError('Invalid object for ExactMatch')


class Regexp(BaseFilter):
    def __init__(self, regexp):
        self.regexp = regexp
        try:
            self._regexp_obj = re_compile(regexp)
        except re_error as error:
            raise FilterValueError(str(error))

    def __repr__(self):
        return 'Regexp({0!r})'.format(self.regexp)

    def serialize(self):
        return {'name': 'regexp', 'regexp': self.regexp}

    def matches(self, value):
        return bool(self._regexp_obj.search(str(value)))

    @classmethod
    def from_obj(cls, obj):
        if 'regexp' in obj:
            return cls(obj['regexp'])

        raise FilterValueError('Invalid object for Regexp')


class Comparison(BaseFilter):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise FilterValueError('Invalid operator: ' + comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparison({0!r}, {1!r})'.format(self.comparator, self.value)

    def serialize(self):
        return {
            'name': 'comparison',
            'comparator': self.comparator,
            'value': self.value,
        }

    @classmethod
    def from_obj(cls, obj):
        if 'comparator' in obj and 'value' in obj:
            return cls(obj['comparator'], obj['value'])

        raise FilterValueError('Invalid object for Comparison')


class Any(BaseFilter):
    def __init__(self, *values):
        self.values = values

    def __repr__(self):
        return 'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def serialize(self):
        return {'name': 'any', 'values': self.values}

    def matches(self, value):
        return value in self.values

    @classmethod
    def from_obj(cls, obj):
        if 'values' in obj and isinstance(obj['values'], list):
            return cls(*obj['values'])
        raise FilterValueError('Invalid object for Any')


class Or(BaseFilter):
    func = any

    def __init__(self, *filters):
        self.filters = filters

    def __repr__(self):
        args = ', '.join(repr(filter) for filter in self.filters)
        return '{0}({1})'.format(type(self).__name__, args)

    def serialize(self):
        return {
            'name': type(self).__name__.lower(),
            'filters': [f.serialize() for f in self.filters],
        }

    def matches(self, value):
        return self.func(f.matches(value) for f in self.filters)

    @classmethod
    def from_obj(cls, obj):
        if 'filters' in obj and isinstance(obj['filters'], list):
            if not obj['filters']:
                raise FilterValueError('Empty filters for And/Or')

            return cls(*[filter_from_obj(f) for f in obj['filters']])

        raise FilterValueError('Invalid object for {0}'.format(cls.__name__))


class And(Or):
    func = all


class Between(BaseFilter):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Between({0!r}, {1!r})'.format(self.a, self.b)

    def serialize(self):
        return {'name': 'between', 'a': self.a, 'b': self.b}

    def matches(self, value):
        return self.a <= value <= self.b

    @classmethod
    def from_obj(cls, obj):
        if 'a' in obj and 'b' in obj:
            return cls(obj['a'], obj['b'])

        raise FilterValueError('Invalid object for Between')


class Not(BaseFilter):
    def __init__(self, filter):     # NOQA A002
        self.filter = filter

    def __repr__(self):
        return 'Not({0!r})'.format(self.filter)

    def serialize(self):
        if isinstance(self.filter, BaseFilter):
            value = self.filter.serialize()
        else:
            value = self.filter
        return {'name': 'not', 'filter': value}

    def matches(self, value):
        if isinstance(self.filter, BaseFilter):
            return not self.filter.matches(value)
        else:
            return value != self.filter

    @classmethod
    def from_obj(cls, obj):
        if 'filter' in obj:
            return cls(filter_from_obj(obj['filter']))

        raise FilterValueError('Invalid object for Not')


class Startswith(BaseFilter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Startswith({0!r})'.format(self.value)

    def serialize(self):
        return {'name': 'startswith', 'value': self.value}

    def matches(self, value):
        return str(value).startswith(self.value)

    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise FilterValueError('Invalid object for Startswith')


class Overlap(BaseFilter):
    def __init__(self, *networks):
        self.networks = networks

    def __repr__(self):
        return '{0}({1})'.format(
            type(self), ', '.join(repr(n) for n in self.networks)
        )

    def serialize(self):
        return {'name': type(self).__name__.lower(), 'networks': self.networks}

    def matches(self, value):
        return any(value in n or n in value for n in self.networks)

    @classmethod
    def from_obj(cls, obj):
        if 'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj['networks'])

        raise FilterValueError('Invalid object for {0}'.format(cls))


class InsideNetwork(Overlap):
    def matches(self, value):
        return any(value in n for n in self.networks)


class InsideOnlyNetwork(InsideNetwork):
    def matches(self, value):
        raise NotImplementedError()


class Empty(BaseFilter):
    def __repr__(self):
        return 'Empty()'

    def serialize(self):
        return {'name': 'empty'}

    def matches(self, value):
        return value is None

    @classmethod
    def from_obj(cls, obj):
        return cls()


def filter_from_obj(obj):
    if isinstance(obj, dict) and 'name' in obj:
        if obj['name'] not in filter_classes:
            raise QueryError('No such filter: {0}'.format(obj['name']))
        return filter_classes[obj['name']].from_obj(obj)
    return obj


# Collect all classes that are subclass of BaseFilter (exclusive)
filter_classes = {
    k.lower(): v
    for k, v in globals().items()
    if type(v) == type and BaseFilter in v.mro()[1:]
}
