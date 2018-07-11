"""Serveradmin - Access Control for Users and Applications

Copyright (c) 2018 InnoGames GmbH
"""

from django.contrib.admin import site, ModelAdmin

from serveradmin.access_control.models import AccessControlGroup


class AccessControlGroupAdmin(ModelAdmin):
    model = AccessControlGroup
    filter_horizontal = ['members', 'applications']


site.register(AccessControlGroup, AccessControlGroupAdmin)
