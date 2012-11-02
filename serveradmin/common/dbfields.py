from django.db import models
from django import forms
from django.core import exceptions

from adminapi.utils import IP
from serveradmin.common import formfields

class IPv4Field(models.Field):
    __metaclass__ = models.SubfieldBase

    def db_type(self, connection):
        return 'integer unsigned'

    def to_python(self, value):
        if isinstance(value, IP):
            return value
        if value is None:
            return None
        return IP(value)

    def get_prep_value(self, value):
        if not isinstance(value, IP):
            if value is None:
                return None
            value = IP(value)
        return value.as_int()

    def get_prep_lookup(self, lookup_type, value):
        valid_lookups = ['exact', 'gt', 'gte', 'lt', 'lte']
        if lookup_type == 'in':
            return [self.get_prep_value(v) for v in value]
        elif lookup_type in valid_lookups:
            return self.get_prep_value(value)
        raise TypeError('Lookup type {0} is not supported'.format(lookup_type))

    def formfield(self, **kwargs):
        return formfields.IPv4Field(**kwargs)

class CommaSeparatedOptionField(models.Field):
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
