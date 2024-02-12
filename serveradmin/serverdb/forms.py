from django import forms
from django.core.exceptions import ValidationError

from serveradmin.serverdb.models import ServertypeAttribute


class ServertypeAdminForm(forms.ModelForm):
    pass


class ServertypeAttributeAdminForm(forms.ModelForm):
    class Meta:
        model = ServertypeAttribute
        fields = [
            'attribute',
            'related_via_attribute',
            'consistent_via_attribute',
            'required',
            'default_value',
            'default_visible',
        ]

    def clean(self):
        # It makes no sense to add inet or supernet attributes to hosts of
        # ip_addr_type null because they would have to be empty anyways.
        inet_attribute = (
            self.cleaned_data['attribute'].type in ('inet', 'inet4', 'inet6', 'supernet') and
            self.instance.servertype.ip_addr_type == 'null'
        )
        if inet_attribute:
            raise ValidationError(
                'Adding an attribute of type inet or supernet when '
                'ip_addr_type is null is not possible!')

        super().clean()
