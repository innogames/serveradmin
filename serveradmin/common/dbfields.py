from ipaddress import IPv4Address, IPv6Address

from django.db import models
from django import forms
from django.core import exceptions

from serveradmin.common import formfields


class IPv4Field(models.Field):
    __metaclass__ = models.SubfieldBase

    def db_type(self, connection):
        return 'integer unsigned'

    def to_python(self, value):
        if isinstance(value, IPv4Address):
            return value
        if value is None:
            return None
        if value == '':
            return None
        return IPv4Address(value)

    def get_prep_value(self, value):
        if not isinstance(value, IPv4Address):
            if value is None:
                return None
            value = IPv4Address(value)
        return int(value)

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type == 'isnull':
            return bool(value)
        if lookup_type in ('in', 'range'):
            return [self.get_prep_value(v) for v in value]
        if lookup_type in ('exact', 'gt', 'gte', 'lt', 'lte'):
            return self.get_prep_value(value)

        raise TypeError('Lookup type {0} is not supported'.format(lookup_type))

    def formfield(self, **kwargs):
        return formfields.IPv4Field(**kwargs)


class IPv6Field(models.Field):
    __metaclass__ = models.SubfieldBase

    def db_type(self, connection):
        return 'BINARY(16)'

    def to_python(self, value):
        if isinstance(value, IPv6Address):
            return value
        if value is None:
            return None
        if value == '':
            return None
        return IPv6Address(bytearray(value))

    def get_prep_value(self, value):
        if not isinstance(value, IPv6Address):
            if value is None:
                return None
            value = IPv6Address(value)
        return value.packed

    def get_prep_lookup(self, lookup_type, value):
        if lookup_type in ('in', 'range'):
            return [self.get_prep_value(v) for v in value]
        if lookup_type in ('exact', 'gt', 'gte', 'lt', 'lte'):
            return self.get_prep_value(value)

        raise TypeError('Lookup type {0} is not supported'.format(lookup_type))

    def formfield(self, **kwargs):
        return formfields.IPv6Field(**kwargs)


class CommaSeparatedOptionField(models.Field):
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if value is None or isinstance(value, list):
            return value
        return value.split(',')

    def get_prep_value(self, value):
        return ','.join(value)

    def validate(self, value, model_instance):
        _valid_options = dict(self._choices)
        for val in value:
            if val not in _valid_options:
                msg = self.error_messages['invalid_choice'] % value
                raise exceptions.ValidationError(msg)
        return True

    def formfield(self, **kwargs):
        kwargs['choices'] = self._choices
        kwargs['widget'] = forms.CheckboxSelectMultiple()
        return forms.MultipleChoiceField(**kwargs)


class IPv4CIDRField(models.Field):
    empty_strings_allowed = False
    description = "IPv4 CIDR"

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 18
        models.Field.__init__(self, *args, **kwargs)

    def get_internal_type(self):
        return "CharField"

    def formfield(self, **kwargs):
        defaults = {'form_class': formfields.IPv4CIDRField}
        defaults.update(kwargs)
        return super(IPv4CIDRField, self).formfield(**defaults)
