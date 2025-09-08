from django import forms
from django.core.exceptions import ValidationError
from django.db.models.aggregates import Count

from serveradmin.serverdb.models import ServertypeAttribute, Attribute, ServerStringAttribute


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
            self.cleaned_data['attribute'].type in ('inet', 'supernet') and
            self.instance.servertype.ip_addr_type == 'null'
        )
        if inet_attribute:
            raise ValidationError(
                'Adding an attribute of type inet or supernet when '
                'ip_addr_type is null is not possible!')

        super().clean()


class AttributeAdminForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = '__all__'

    def clean(self):
        attr_type = self.cleaned_data.get('type') or self.instance.type  # New or existing attribute ?

        if attr_type != 'relation' and self.cleaned_data.get('target_servertype') is not None:
            raise ValidationError('Attribute type must be relation when target servertype is selected!')

        if attr_type == 'inet' and self.cleaned_data.get('multi') is True:
            raise ValidationError('Multi attributes of type inet are not supported!')

        if self.cleaned_data.get('multi') is False:
            any_attrs_have_multiple_values = ServerStringAttribute.get_model(self.instance.type).objects.filter(
                attribute_id=self.instance.attribute_id).values('server_id').annotate(
                occurences=Count('server_id')).filter(occurences__gt=1).exists()
            if any_attrs_have_multiple_values:
                raise ValidationError(
                    'Refusing to make attribute type single because one ore more objects still have multiple values!')

        super().clean()
