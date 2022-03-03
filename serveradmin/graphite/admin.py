"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from django.contrib import admin

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


admin.site.register(Collection, CollectionAdmin)
