from django.contrib import admin

from serveradmin.graphite.models import Collection, Template, Variation

class TemplateInline(admin.TabularInline):
    model = Template

class VariationInline(admin.TabularInline):
    model = Variation

class CollectionAdmin(admin.ModelAdmin):
    inlines = (TemplateInline, VariationInline)

admin.site.register(Collection, CollectionAdmin)
