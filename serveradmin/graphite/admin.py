"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from django import forms
from django.contrib import admin

from serveradmin.graphite.models import (
    Collection,
    Numeric,
    Relation,
    Template,
    Variation,
)


def _validate_params(params):
    params = params.split('&')
    params_keys = [
        param.split('=')[0] if '=' in param else param
        for param in params
    ]
    if len(params_keys) != len(set(params_keys)):
        raise forms.ValidationError(
            'Duplicate parameters are not allowed'
        )


class InlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for data in self.cleaned_data:
            params = data.get('params')
            if not params:
                continue
            _validate_params(params)
        return self.cleaned_data


class TemplateInline(admin.TabularInline):
    model = Template


class VariationInline(admin.TabularInline):
    model = Variation
    formset = InlineFormSet


class NumericInline(admin.TabularInline):
    model = Numeric
    formset = InlineFormSet


class RelationInline(admin.TabularInline):
    model = Relation


class CollectionAdmin(admin.ModelAdmin):
    inlines = (TemplateInline, VariationInline, NumericInline, RelationInline)

    list_display = ['name', 'overview', 'created_at']
    search_fields = ['name']
    list_filter = ['overview']


class CollectionAdminForm(forms.ModelForm):

    def clean_params(self):
        _validate_params(self.cleaned_data['params'])
        return self.cleaned_data['params']


admin.site.register(Collection, CollectionAdmin, form=CollectionAdminForm)
