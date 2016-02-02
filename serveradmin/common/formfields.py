import re

from django import forms
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

from adminapi.utils import IP, IPv6

class IPv4Field(forms.GenericIPAddressField):
    def __init__(self, **kwargs):
        if 'initial' in kwargs:
            if isinstance(kwargs['initial'], IP):
                kwargs['initial'] = kwargs['initial'].as_ip()
        super(IPv4Field, self).__init__(**kwargs)

    def clean(self, value):
        ip_string = super(IPv4Field, self).clean(value)
        if ip_string:
            return IP(ip_string)
        return None

class IPv6Field(forms.Field):
    def __init__(self, **kwargs):
        if 'initial' in kwargs:
            if isinstance(kwargs['initial'], IPv6):
                kwargs['initial'] = kwargs['initial'].as_ip()
        super(IPv6Field, self).__init__(**kwargs)

    def clean(self, value):
        ip_string = super(IPv6Field, self).clean(value)
        if ip_string:
            try:
                return IPv6(ip_string)
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
