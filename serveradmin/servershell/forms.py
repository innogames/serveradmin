from ipaddress import ip_address

from django import forms

from serveradmin.serverdb.models import Project, ServerType, ServerObject

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

        if ServerObject.objects.filter(
                hostname=self.cleaned_data['hostname']
            ).exists():

            msg = 'Hostname already taken.'
            self._errors['hostname'] = self.error_class([msg])

        if self.cleaned_data.get('check_ip'):
            if ServerObject.objects.filter(
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
    servertype = forms.ModelChoiceField(queryset=ServerType.objects.all())

    def get_servertype(self):
        return self.cleaned_data['servertype']
