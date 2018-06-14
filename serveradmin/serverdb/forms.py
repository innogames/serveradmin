from django import forms

from serveradmin.serverdb.models import Server, Servertype


class ServerForm(forms.ModelForm):
    _servertype = forms.ModelChoiceField(
        queryset=Servertype.objects.filter(), empty_label=None
    )

    class Meta:
        model = Server
        fields = ('_servertype', 'hostname', 'intern_ip')
