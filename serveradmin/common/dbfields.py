from django.db import models

from adminapi.utils import IP
from serveradmin.common import formfields

class IPv4Field(models.Field):
    __metaclass__ = models.SubfieldBase

    def db_type(self, connection):
        return 'integer unsigned'

    def to_python(self, value):
        if isinstance(value, IP):
            return value
        return IP(value)

    def get_prep_value(self, value):
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
