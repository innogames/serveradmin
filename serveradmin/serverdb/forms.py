from django import forms

from serveradmin.serverdb.models import Server


class ServerForm(forms.ModelForm):
    class Meta:
        model = Server
        fields = ('_servertype', '_project', 'hostname', 'intern_ip')
