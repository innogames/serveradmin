# This module must only include the filter classes.  Everything defined
# in here are going to collected as the filters.


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

    def _serialize(self):
        return {'name': 'exactmatch', 'value': self.value}


class Regexp(BaseFilter):
    def __init__(self, regexp):
        self.regexp = regexp

    def __repr__(self):
        return 'Regexp({0!r})'.format(self.regexp)

    def _serialize(self):
        return {'name': 'regexp', 'regexp': self.regexp}


class Comparison(BaseFilter):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise ValueError('Invalid comparison operator: ' + comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparison({0!r}, {1!r})'.format(self.comparator, self.value)

    def _serialize(self):
        return {
            'name': 'comparison',
            'comparator': self.comparator,
            'value': self.value,
        }


class Any(BaseFilter):
    def __init__(self, *values):
        self.values = values

    def __repr__(self):
        return 'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def _serialize(self):
        return {'name': 'any', 'values': self.values}


class _AndOr(BaseFilter):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = ', '.join(repr(filter) for filter in self.filters)
        return '{0}({1})'.format(self.name.capitalize(), args)

    def _serialize(self):
        return {
            'name': self.name,
            'filters': [f._serialize() for f in self.filters],
        }


class And(_AndOr):
    name = 'and'


class Or(_AndOr):
    name = 'or'


class Between(BaseFilter):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Between({0!r}, {1!r})'.format(self.a, self.b)

    def _serialize(self):
        return {'name': 'between', 'a': self.a, 'b': self.b}


class Not(BaseFilter):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Not({0!r})'.format(self.filter)

    def _serialize(self):
        return {'name': 'not', 'filter': self.filter._serialize()}


class Startswith(BaseFilter):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Startswith({0!r})'.format(self.value)

    def _serialize(self):
        return {'name': 'startswith', 'value': self.value}


class Overlap(BaseFilter):
    def __init__(self, *networks):
        self.networks = networks

    def __repr__(self):
        args = ', '.join(repr(net) for net in self.networks)
        return 'Overlap({0})'.format(args)

    def _serialize(self):
        return {'name': 'overlap', 'networks': self.networks}


class InsideNetwork(BaseFilter):
    def __init__(self, *networks):
        self.networks = networks

    def __repr__(self):
        args = ', '.join(repr(net) for net in self.networks)
        return 'InsideNetwork({0})'.format(args)

    def _serialize(self):
        return {'name': 'insidenetwork', 'networks': self.networks}


class Empty(BaseFilter):
    def __repr__(self):
        return 'Empty()'

    def _serialize(self):
        return {'name': 'empty'}


def _prepare_filter(filter):
    return filter if isinstance(filter, BaseFilter) else ExactMatch(filter)


filter_classes = {
    d.lower(): globals()[d] for d in dir() if not d.startswith('_')
}
