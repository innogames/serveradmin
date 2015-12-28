import re
from ipaddress import IPv4Address, IPv6Address

from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

class IPv4Field(forms.GenericIPAddressField):
    def __init__(self, **kwargs):
        if 'initial' in kwargs:
            if isinstance(kwargs['initial'], IPv4Address):
                kwargs['initial'] = str(kwargs['initial'])

        super(IPv4Field, self).__init__(**kwargs)

    def clean(self, value):
        ip_string = super(IPv4Field, self).clean(value)
        if ip_string:
            return IPv4Address(ip_string)
        return None

class IPv6Field(forms.Field):
    def __init__(self, **kwargs):
        if 'initial' in kwargs:
            if isinstance(kwargs['initial'], IPv6Address):
                kwargs['initial'] = str(kwargs['initial'])

        super(IPv6Field, self).__init__(**kwargs)

    def clean(self, value):
        ip_string = super(IPv6Field, self).clean(value)
        if ip_string:
            try:
                return IPv6Address(ip_string)
            except ValueError:
                raise ValidationError('Not a valid IPv6 Address')
        return None

ipv4cidr_re = re.compile('^((2[0-5]{2}|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}(2[0-5]{2}|2[0-4]\d|1\d{2}|[1-9]\d|\d)/(3[012]|[12]\d|\d)$')
validate_ipv4_cidr = RegexValidator(ipv4cidr_re, 'Enter a valid IPv4 CIDR', 'invalid')
class IPv4CIDRField(forms.CharField):
    default_error_messages = {
        'invalid': u'Enter a valid IPv4 CIDR',
    }
    default_validators = [validate_ipv4_cidr]
