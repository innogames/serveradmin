class ExactMatch(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'ExactMatch({0!r})'.format(self.value)

    def _serialize(self):
        return {'name': 'exactmatch', 'value': self.value}

class Regexp(object):
    def __init__(self, regexp):
        self.regexp = regexp

    def __repr__(self):
        return 'Regexp({0!r})'.format(self.regexp)

    def _serialize(self):
        return {'name': 'regexp', 'regexp': self.regexp}

class Comparism(object):
    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise ValueError('Invalid comparism operator: ' + comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparism({0!r}, {1!r})'.format(self.comparator, self.value)

    def _serialize(self):
        return {'name': 'comparism', 'comparator': self.comparator,
                'value': self.value}

class Any(object):
    def __init__(self, *values):
        self.values = values

    def __repr__(self):
        return 'Any({0})'.format(', '.join(repr(val) for val in self.values))

    def _serialize(self):
        return {'name': 'any', 'values': self.values}

class _AndOr(object):
    def __init__(self, *filters):
        self.filters = map(_prepare_filter, filters)

    def __repr__(self):
        args = ', '.join(repr(filter) for filter in self.filters)
        return '{0}({1})'.format(self.name.capitalize(), args)

    def _serialize(self):
        return {'name': self.name, 'filters': [f._serialize() for f in
            self.filters]}

class And(_AndOr):
    name = 'and'

class Or(_AndOr):
    name = 'or'

class Between(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return 'Between({0!r}, {1!r})'.format(self.a, self.b)

    def _serialize(self):
        return {'name': 'between', 'a': self.a, 'b': self.b}

class Not(object):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Not({0!r})'.format(self.filter)
    
    def _serialize(self):
        return {'name': 'not', 'filter': self.filter._serialize()}

class Optional(object):
    def __init__(self, filter):
        self.filter = _prepare_filter(filter)

    def __repr__(self):
        return 'Optional({0!r})'.format(self.filter)

    def _serialize(self):
        return {'name': 'optional', 'filter': self.filter._serialize()}

def _prepare_filter(filter):
    return (ExactMatch(filter) if isinstance(filter, (int, basestring, bool))
            else filter)
