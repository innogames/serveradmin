from django import forms

from adminapi.utils import IP

class IPv4Field(forms.IPAddressField):
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
