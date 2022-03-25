"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from django.contrib import admin
from django import forms
from serveradmin.graphite.models import (
    Collection,
    Numeric,
    Relation,
    Template,
    Variation,
)


class TemplateInline(admin.TabularInline):
    model = Template


class VariationInline(admin.TabularInline):
    model = Variation


class NumericInline(admin.TabularInline):
    model = Numeric


class RelationInline(admin.TabularInline):
    model = Relation


class CollectionAdmin(admin.ModelAdmin):
    inlines = (TemplateInline, VariationInline, NumericInline, RelationInline)

    list_display = ['name', 'overview', 'created_at']
    search_fields = ['name']
    list_filter = ['overview']


class CollectionAdminForm(forms.ModelForm):

    def clean_params(self):
        params = self.cleaned_data['params'].split('&')
        params_keys = [
            param.split('=')[0] if '=' in param else param for param in params
        ]
        if len(params_keys) != len(set(params_keys)):
            raise forms.ValidationError('Duplicate parameters are not allowed')
        return self.cleaned_data['params']


admin.site.register(Collection, CollectionAdmin, form=CollectionAdminForm)
