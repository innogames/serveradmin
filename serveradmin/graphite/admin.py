from django.contrib import admin

from serveradmin.graphite.models import (
    Collection,
    Template,
    Variation,
    Numeric,
)


class TemplateInline(admin.TabularInline):
    model = Template


class VariationInline(admin.TabularInline):
    model = Variation


class NumericInline(admin.TabularInline):
    model = Numeric


class CollectionAdmin(admin.ModelAdmin):
    inlines = (TemplateInline, VariationInline, NumericInline)


admin.site.register(Collection, CollectionAdmin)
