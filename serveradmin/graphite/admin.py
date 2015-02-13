from django.contrib import admin

from serveradmin.graphite.models import GraphTemplate, GraphVariation, GraphGroup

class GraphTemplateInline(admin.TabularInline):
    model = GraphTemplate

class GraphVariationInline(admin.TabularInline):
    model = GraphVariation

class GraphGroupAdmin(admin.ModelAdmin):
    inlines = (GraphTemplateInline, GraphVariationInline)

admin.site.register(GraphGroup, GraphGroupAdmin)
