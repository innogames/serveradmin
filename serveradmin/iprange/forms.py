from django import forms
from django.core import validators, exceptions

from adminapi.utils import Network
from serveradmin.common import formfields
from serveradmin.serverdb.models import Segment
from serveradmin.iprange.models import IPRange, IP_CHOICES

class IPRangeForm(forms.Form):
    range_id = forms.CharField()
    segment = forms.ModelChoiceField(queryset=Segment.objects.all())
    ip_type = forms.ChoiceField(choices=IP_CHOICES, label='Type')
    cidr = forms.CharField(required=False, label='CIDR')
    start = formfields.IPv4Field(required=False, label='Start IP')
    end = formfields.IPv4Field(required=False, label='End IP')
    gateway = formfields.IPv4Field(required=False, label='Default gateway')
    internal_gateway = formfields.IPv4Field(required=False, label='Internal gateway')
    belongs_to = forms.ModelChoiceField(queryset=IPRange.objects.all(),
            empty_label='None', required=False)

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
        if not data['cidr']:
            if not data['start'] or not data['end']:
                raise forms.ValidationError('Please provide CIDR or start/end')
            if data['start'] > data['end']:
                raise forms.ValidationError('Start must not be greater than '
                                            'end')
            return data
        
        try:
            ip_part, net_part = data['cidr'].split('/')
            validators.validate_ipv4_address(ip_part)
            if not (0 <= int(net_part) <= 32):
                raise ValueError('Invalid net part')
        except (ValueError, exceptions.ValidationError):
            raise forms.ValidationError('Invalid CIDR')

        net = Network(data['cidr'])
        if ((data['start'] and net.min_ip != data['start']) or
                data['end'] and net.max_ip != data['end']):
            raise forms.ValidationError('CIDR does not match other fields')
        
        data['start'] = net.min_ip
        data['end'] = net.max_ip

        return data
