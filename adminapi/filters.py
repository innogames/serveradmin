from re import compile as re_compile, error as re_error

from adminapi.base import STR_BASED_DATATYPES, QueryError

try:
    STR_DATATYPES = (str, unicode)
except NameError:
    STR_DATATYPES = (str,)


class FilterValueError(QueryError, ValueError):
    pass


class BaseFilter(object):
    def __init__(self, value):
        if type(self) == BaseFilter and isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            pass
        elif isinstance(value, tuple(s[0] for s in STR_BASED_DATATYPES)):
            pass
        elif isinstance(value, STR_DATATYPES):
            for char in '\'"()':
                if char in value:
                    raise FilterValueError(
                        '"{}" character is not allowed on filter values'
                        .format(char)
                    )
        else:
            raise FilterValueError(
                'Filter value cannot be {}'.format(type(value).__name__)
            )

        self.value = value

    def __and__(self, other):
        return All(self, other)

    def __or__(self, other):
        return Any(self, other)

    def __repr__(self):
        if type(self) == BaseFilter:
            return repr(self.value)
        return '{}({!r})'.format(type(self).__name__, self.value)

    def serialize(self):
        if type(self) == BaseFilter:
            return self.value
        return {type(self).__name__: self.value}

    @staticmethod
    def deserialize(obj):
        if not isinstance(obj, dict):
            return BaseFilter(obj)

        if len(obj) != 1:
            raise FilterValueError('Malformatted filter')

        for name, value in obj.items():
            break

        for filter_class in filter_classes:
            if filter_class.__name__ == name:
                break
        else:
            raise FilterValueError('No such filter: {0}'.format(name))

        return filter_class.deserialize_value(value)

    @classmethod
    def deserialize_value(cls, value):
        return cls(value)

    def matches(self, value):
        return value == self.value


class ExactMatch(BaseFilter):
    """Deprecated"""

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise FilterValueError('Invalid object for ExactMatch')


class Regexp(BaseFilter):
    """Match the attribute against a regular expression"""

    def __init__(self, value):
        self.value = value
        try:
            self._regexp_obj = re_compile(value)
        except re_error as error:
            raise FilterValueError(str(error))

    def matches(self, value):
        return bool(self._regexp_obj.search(str(value)))

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'regexp' in obj:
            return cls(obj['regexp'])

        raise FilterValueError('Invalid object for Regexp')


class GreaterThanOrEquals(BaseFilter):
    """Filter the attribute greater than or equals to the value"""

    def matches(self, value):
        return self.value >= value


class GreaterThan(GreaterThanOrEquals):
    """Filter the attribute greater than the value"""

    def matches(self, value):
        return self.value > value


class LessThanOrEquals(BaseFilter):
    """Filter the attribute less than or equals to the value"""

    def matches(self, value):
        return self.value <= value


class LessThan(LessThanOrEquals):
    """Filter the attribute less than the value"""

    def matches(self, value):
        return self.value < value


class Comparison(BaseFilter):
    """Deprecated, use (Greater|Less)Than[OrEquals]() instead"""

    def __init__(self, comparator, value):
        if comparator not in ('<', '>', '<=', '>='):
            raise FilterValueError('Invalid operator: ' + comparator)
        self.comparator = comparator
        self.value = value

    def __repr__(self):
        return 'Comparison({0!r}, {1!r})'.format(self.comparator, self.value)

    def serialize(self):
        return {type(self).__name__: [self.comparator, self.value]}

    @classmethod
    def deserialize_value(cls, value):
        if not isinstance(value, list) or len(value) != 2:
            raise FilterValueError(
                'Invalid value for {}()'.format(cls.__name__)
            )
        return cls(value[0], value[1])

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'comparator' in obj and 'value' in obj:
            return cls(obj['comparator'], obj['value'])

        raise FilterValueError('Invalid object for Comparison')


class Any(BaseFilter):
    """Check if the attribute satisfies any of the conditions"""
    func = any

    def __init__(self, *values):
        self.values = [
            v if isinstance(v, BaseFilter) else BaseFilter(v)
            for v in values
        ]

    def __repr__(self):
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(repr(v) for v in self.values),
        )

    def serialize(self):
        return {type(self).__name__: [v.serialize() for v in self.values]}

    @classmethod
    def deserialize_value(cls, value):
        if not isinstance(value, list):
            raise FilterValueError(
                'Invalid value for {}()'.format(cls.__name__)
            )
        return cls(*[cls.deserialize(v) for v in value])

    def matches(self, value):
        return self.func(v.matches(value) for v in self.values)

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'values' in obj and isinstance(obj['values'], list):
            return cls(*obj['values'])
        raise FilterValueError('Invalid object for Any')


class Or(Any):
    """Deprecated, use Any() instead"""

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'filters' in obj and isinstance(obj['filters'], list):
            if not obj['filters']:
                raise FilterValueError('Empty filters for And/Or')

            return cls(*[filter_from_obj(f) for f in obj['filters']])

        raise FilterValueError('Invalid object for {0}'.format(cls.__name__))


class All(Any):
    """Check if an attribute satisfies all of the conditions"""
    func = all


class And(All, Or):
    """Deprecated, use All() instead"""
    pass


class Not(BaseFilter):
    """Negate the given filter"""

    def __init__(self, value):
        if isinstance(value, BaseFilter):
            self.value = value
        else:
            self.value = BaseFilter(value)

    def serialize(self):
        return {type(self).__name__: self.value.serialize()}

    @classmethod
    def deserialize_value(cls, value):
        return cls(cls.deserialize(value))

    def matches(self, value):
        return not self.value.matches(value)

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'filter' in obj:
            return cls(filter_from_obj(obj['filter']))

        raise FilterValueError('Invalid object for Not')


class Overlaps(BaseFilter):
    """Check if the attribute is overlapping"""

    def matches(self, value):
        return value in self.value or self.value in value


class Overlap(Overlaps):
    """Deprecated, use Overlaps() instead"""

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'networks' in obj and isinstance(obj['networks'], (tuple, list)):
            return cls(*obj['networks'])

        raise FilterValueError('Invalid object for {0}'.format(cls))


class Contains(Overlaps):
    """Check if the attribute contains"""

    def matches(self, value):
        return self.value in value


class StartsWith(Contains):
    """Check if the value starts with"""

    def matches(self, value):
        return str(value).startswith(self.value)


class Startswith(StartsWith):
    """Deprecated, use StartsWith() instead"""

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        if 'value' in obj:
            return cls(obj['value'])

        raise FilterValueError('Invalid object for Startswith')


class ContainedBy(Overlaps):
    """Check if the attribute is contained by the given value"""

    def matches(self, value):
        return value in self.value


class InsideNetwork(ContainedBy, Overlap):
    """Deprecated, use ContainedBy() instead"""
    pass


class ContainedOnlyBy(Overlaps):
    """Check if an IP address is inside a network and no other network
    is in between"""

    def matches(self, value):
        raise NotImplementedError()


class Empty(BaseFilter):
    """Check if the attribute exists"""

    def __init__(self):
        pass

    def __repr__(self):
        return 'Empty()'

    def serialize(self):
        return {type(self).__name__: None}

    @classmethod
    def deserialize_value(cls, value):
        if value is not None:
            raise FilterValueError(
                'Invalid value for {}()'.format(cls.__name__)
            )
        return cls()

    def matches(self, value):
        return value is None

    # TODO Remove
    @classmethod
    def from_obj(cls, obj):
        return cls()


# TODO Remove
def filter_from_obj(obj):
    if isinstance(obj, dict) and 'name' in obj:
        for filter_class in filter_classes:
            if hasattr(filter_class, 'from_obj'):
                if filter_class.__name__.lower() == obj['name']:
                    return filter_class.from_obj(obj)
    return BaseFilter.deserialize(obj)


# Collect all classes that are subclass of BaseFilter (exclusive)
filter_classes = [
    v
    for v in globals().values()
    if type(v) == type and BaseFilter in v.mro()[1:]
]
