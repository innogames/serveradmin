from ipaddress import IPv4Network, IPv6Network

from django import forms
from django.core import validators, exceptions

from serveradmin.common import formfields
from serveradmin.serverdb.models import Segment
from serveradmin.iprange.models import IPRange, IP_CHOICES

class IPRangeForm(forms.Form):
    range_id = forms.CharField()
    segment = forms.ModelChoiceField(queryset=Segment.objects.filter())
    ip_type = forms.ChoiceField(choices=IP_CHOICES, label='Type')
    vlan = forms.IntegerField(required=False, label='VLAN', min_value=1, max_value=4095)
    belongs_to = forms.ModelChoiceField(queryset=IPRange.objects.all(),
            empty_label='None', required=False)
    cidr = forms.CharField(required=False, label='IPv4 CIDR')
    gateway = formfields.IPv4Field(required=False, label='Default IPv4 gateway')
    internal_gateway = formfields.IPv4Field(required=False, label='Internal IPv4 gateway')
    cidr6 = forms.CharField(required=False, label='IPv6 CIDR')
    gateway6 = formfields.IPv6Field(required=False, label='Default IPv6 gateway')
    internal_gateway6 = formfields.IPv6Field(required=False, label='Internal IPv6 gateway')

    def __init__(self, *args, **kwargs):
        self.iprange = kwargs.pop('iprange', None)
        super(IPRangeForm, self).__init__(*args, **kwargs)

    def clean_range_id(self):
        data = self.cleaned_data

        check = not self.iprange or self.iprange.range_id != data['range_id']
        if check and IPRange.objects.filter(range_id=data['range_id']).count():
                raise forms.ValidationError('Range id is already taken')
        return data['range_id']

    def clean(self):
        data = self.cleaned_data
        if data['cidr']:
            try:
                ip_part, net_part = data['cidr'].split('/')
                validators.validate_ipv4_address(ip_part)
                if not (0 <= int(net_part) <= 32):
                    raise ValueError('Invalid net part')
            except (ValueError, exceptions.ValidationError):
                raise forms.ValidationError('Invalid CIDR')

            net = IPv4Network(data['cidr'])

            data['start'] = net.network_address
            data['end'] = net.broadcast_address
        else:
            data['start'] = None
            data['end'] = None

        if data['cidr6']:
            try:
                ip6, net_len = data['cidr6'].split('/')
                validators.validate_ipv6_address(ip6)
                if not (0 <= int(net_len) <= 128):
                    raise ValueError('Invalid prefix length')
            except (ValueError, exceptions.ValidationError):
                raise forms.ValidationError('Invalid IPv6 Network')

            net = IPv6Network(data['cidr6'])
            data['start6'] = net.network_address
            data['end6'] = net.broadcast_address
        else:
            data['start6'] = None
            data['end6'] = None

        return data
