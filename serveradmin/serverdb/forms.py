import re

from ipaddress import ip_address

from django import forms

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
)


class AddServertypeForm(forms.ModelForm):
    class Meta:
        model = Servertype
        fields = ('servertype_id', 'description', )


class AddAttributeForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ('attribute_id', 'type', 'multi')


class EditServertypeAttributeForm(forms.ModelForm):
    attrib_default = forms.CharField(label='Default', required=False)

    class Meta:
        model = ServertypeAttribute
        fields = ('required', 'attrib_default', 'regexp')
        widgets = {
            'regexp': forms.TextInput(attrs={'size': 50})
        }

    def __init__(self, servertype, *args, **kwargs):
        self.servertype = servertype
        super(EditServertypeAttributeForm, self).__init__(*args, **kwargs)

    def clean_regexp(self):
        regexp = self.cleaned_data['regexp']
        if regexp is not None:
            try:
                re.compile(regexp)
            except re.error:
                raise forms.ValidationError('Invalid regular expression')
        return regexp


class AddServertypeAttributeForm(EditServertypeAttributeForm):
    class Meta(EditServertypeAttributeForm.Meta):
        fields = ('_attribute', ) + EditServertypeAttributeForm.Meta.fields


class ServerForm(forms.ModelForm):
    class Meta:
        model = Server
        fields = ('_servertype', '_project', 'hostname', 'intern_ip')

    # Django forms.GenericIPAddressField() doesn't normalises value to
    # and IP address.  We are doing it manually in here as it is the only
    # form we have at the moment.
    def clean_intern_ip(self):
        return ip_address(self.cleaned_data['intern_ip'])
