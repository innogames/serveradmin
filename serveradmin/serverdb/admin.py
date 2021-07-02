"""Serveradmin - Django Admin Setup

Copyright (c) 2019 InnoGames GmbH
"""

from django.contrib import admin

from serveradmin.serverdb.forms import (
    ServertypeAttributeAdminForm,
    ServertypeAdminForm,
)
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ServerRelationAttribute,
    ServerStringAttribute,
    ChangeDelete,
)


class ServertypeAttributeInline(admin.TabularInline):
    form = ServertypeAttributeAdminForm
    model = ServertypeAttribute


class ServertypeAdmin(admin.ModelAdmin):
    form = ServertypeAdminForm
    inlines = (
        ServertypeAttributeInline,
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)

        if obj:
            # Because of the complexity when changing servertypes of existing
            # objects and the little use-cases we have right now we don't
            # support it.
            fields += ('ip_addr_type',)

        return fields


class ServerRelationAttributeInline(admin.TabularInline):
    model = ServerRelationAttribute
    fk_name = 'server'


class ServerStringAttributeInline(admin.TabularInline):
    model = ServerStringAttribute


class ServerAdmin(admin.ModelAdmin):
    inlines = (
        ServerRelationAttributeInline,
        ServerStringAttributeInline,
    )


class AttributeAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)

        # Because of the complexity when changing attribute types of existing
        # objects and the little use-cases we have right now we don't
        # support it.
        if obj:
            fields += ('type',)

        return fields


admin.site.register(Servertype, ServertypeAdmin)
admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Server, ServerAdmin)
admin.site.register(ChangeDelete)
