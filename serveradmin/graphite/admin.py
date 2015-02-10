from django.contrib import admin

from serveradmin.graphite.models import *

class GraphTimeRangeInline(admin.TabularInline):
    model = GraphTimeRange

class GraphTemplateInline(admin.TabularInline):
    model = GraphTemplate

class GraphGroupAdmin(admin.ModelAdmin):
    inlines = (GraphTimeRangeInline, GraphTemplateInline)

admin.site.register(GraphGroup, GraphGroupAdmin)
