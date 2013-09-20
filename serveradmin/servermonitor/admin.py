from django.contrib import admin

from serveradmin.servermonitor.models import GraphDescription


class GraphDescriptionAdmin(admin.ModelAdmin):
    fields = ['graph_name', 'description']

admin.site.register(GraphDescription, GraphDescriptionAdmin)
