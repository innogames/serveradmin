"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

from re import compile as re_compile
from re import error as re_error

from adminapi.datatype import STR_BASED_DATATYPES
from adminapi.exceptions import FilterValueError


class BaseFilter(object):
    def __init__(self, value):
        ok_datatypes = tuple([bool, int, float] + [s[0] for s in STR_BASED_DATATYPES])
        if type(self) is BaseFilter and isinstance(value, ok_datatypes):
            pass
        elif isinstance(value, str):
            for char in '\'"':
                if char in value:
                    raise FilterValueError('"{}" character is not allowed on filter values'.format(char))
        else:
            raise FilterValueError('Filter value cannot be {}'.format(type(value).__name__))

        self.value = value

    def __and__(self, other):
        return All(self, other)

    def __or__(self, other):
        return Any(self, other)

    def __repr__(self):
        if type(self) is BaseFilter:
            return repr(self.value)
        return '{}({!r})'.format(type(self).__name__, self.value)

    def serialize(self):
        if type(self) is BaseFilter:
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

    def destiny(self):
        return None


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


class Any(BaseFilter):
    """Check if the attribute satisfies any of the conditions"""

    func = any

    def __init__(self, *values):
        self.values = [v if isinstance(v, BaseFilter) else BaseFilter(v) for v in values]

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
            raise FilterValueError('Invalid value for {}()'.format(cls.__name__))
        return cls(*[cls.deserialize(v) for v in value])

    def matches(self, value):
        return self.func(v.matches(value) for v in self.values)

    def destiny(self):
        if not self.values:
            return False
        return None


class All(Any):
    """Check if an attribute satisfies all of the conditions"""

    func = all

    def destiny(self):
        if not self.values:
            return True
        return None


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

    def destiny(self):
        value_destiny = self.value.destiny()
        if isinstance(value_destiny, bool):
            return not value_destiny
        return None


class Overlaps(BaseFilter):
    """Check if the attribute is overlapping"""

    def matches(self, value):
        return value in self.value or self.value in value


class Contains(Overlaps):
    """Check if the attribute contains"""

    def matches(self, value):
        return self.value in value


class StartsWith(Contains):
    """Check if the value starts with"""

    def matches(self, value):
        return str(value).startswith(self.value)


class ContainedBy(Overlaps):
    """Check if the attribute is contained by the given value"""

    def matches(self, value):
        return value in self.value


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
            raise FilterValueError('Invalid value for {}()'.format(cls.__name__))
        return cls()

    def matches(self, value):
        return value is None


# Collect all classes that are subclass of BaseFilter (exclusive)
filter_classes = [v for v in globals().values() if type(v) is type and BaseFilter in v.mro()[1:]]