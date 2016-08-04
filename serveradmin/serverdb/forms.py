from ipaddress import ip_address

from django import forms

from serveradmin.serverdb.models import Server


class ServerForm(forms.ModelForm):
    class Meta:
        model = Server
        fields = ('_servertype', '_project', 'hostname', 'intern_ip')

    # Django forms.GenericIPAddressField() doesn't normalises value to
    # and IP address.  We are doing it manually in here as it is the only
    # form we have at the moment.
    def clean_intern_ip(self):
        return ip_address(self.cleaned_data['intern_ip'])
