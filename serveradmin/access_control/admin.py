"""Serveradmin - Access Control for Users and Applications

Copyright (c) 2019 InnoGames GmbH
"""

from django.contrib.admin import ModelAdmin, site

from serveradmin.access_control.models import AccessControlGroup


class AccessControlGroupAdmin(ModelAdmin):
    model = AccessControlGroup

    list_display = ['name', 'query', 'is_whitelist']
    search_fields = ['name']
    list_filter = ['is_whitelist']

    filter_horizontal = ['members', 'applications']


site.register(AccessControlGroup, AccessControlGroupAdmin)
