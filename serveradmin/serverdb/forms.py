import re

from ipaddress import ip_address

from django import forms

from serveradmin.serverdb.models import (
    Project,
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


class BaseServerForm(forms.Form):
    project = forms.ModelChoiceField(queryset=Project.objects.all())
    hostname = forms.CharField()
    intern_ip = forms.GenericIPAddressField()
    check_ip = forms.BooleanField(required=False)

    def clean(self):

        # Django forms.GenericIPAddressField() doesn't normalises value to
        # and IP address.  We are doing it manually in here as it is the only
        # form we have at the moment.
        self.cleaned_data['intern_ip'] = ip_address(
            self.cleaned_data['intern_ip']
        )

        if Server.objects.filter(
            hostname=self.cleaned_data['hostname']
        ).exists():

            msg = 'Hostname already taken.'
            self._errors['hostname'] = self.error_class([msg])

        if self.cleaned_data.get('check_ip'):
            if Server.objects.filter(
                intern_ip=self.cleaned_data['intern_ip']
            ).exists():

                msg = 'IP already taken.'
                self._errors['intern_ip'] = self.error_class([msg])

        fixed_project = self.get_servertype().fixed_project
        if fixed_project and self.cleaned_data['project'] != fixed_project:
            msg = 'Project has to be "{0}".'.format(fixed_project)
            self._errors['project'] = self.error_class([msg])

        return self.cleaned_data


class CloneServerForm(BaseServerForm):
    def __init__(self, servertype, *args, **kwargs):
        super(CloneServerForm, self).__init__(*args, **kwargs)
        self.servertype = servertype

    def get_servertype(self):
        return self.servertype


class NewServerForm(BaseServerForm):
    servertype = forms.ModelChoiceField(queryset=Servertype.objects.all())

    def get_servertype(self):
        return self.cleaned_data['servertype']
