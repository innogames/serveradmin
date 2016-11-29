from django import forms

from serveradmin.serverdb.models import Server, Servertype


class ServerForm(forms.ModelForm):
    _servertype = forms.ModelChoiceField(
        queryset=Servertype.objects, empty_label=None
    )

    class Meta:
        model = Server
        fields = (
            '_servertype', '_project', '_segment', 'hostname', 'intern_ip'
        )
