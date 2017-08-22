from django.contrib.admin import site, ModelAdmin

from serveradmin.access_control.models import AccessControlGroup


class AccessControlGroupAdmin(ModelAdmin):
    model = AccessControlGroup
    filter_horizontal = ['members']


site.register(AccessControlGroup, AccessControlGroupAdmin)
