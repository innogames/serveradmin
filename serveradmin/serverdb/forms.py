from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ServertypeAdminForm(forms.ModelForm):
    def clean(self):
        if self.cleaned_data.get('ip_addr_type') == 'null':
            supernet_and_required = self.instance.attributes.filter(
                required=True,
                attribute__type='supernet'
            ).only('attriute_id').values_list('attribute_id', flat=True)
            if supernet_and_required.exists():
                raise ValidationError(_(
                        'ip_addr_type for Servertype must not be "null" '
                        'if any attribute of type supernet is required '
                        'but %(attrs)s is/are!'
                    ),
                    code='invalid',
                    params={
                        'attrs': ','.join(supernet_and_required)
                    })
        super().clean()


class ServertypeAttributeAdminForm(forms.ModelForm):
    def clean(self):
        supernet_and_required = (
            self.instance.attribute.type == 'supernet' and
            self.instance.servertype.ip_addr_type == 'null' and
            self.cleaned_data.get('required') is True
        )
        if supernet_and_required:
            raise ValidationError(_(
                    'Attributes of type %(type)s can not be required if '
                    'ip_addr_type of Servertype is null!'
                ),
                code='invalid',
                params={
                    'attribute': self.instance.attribute.attribute_id,
                    'type': self.instance.attribute.type,
                })
        super().clean()
