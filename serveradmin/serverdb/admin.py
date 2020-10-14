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


admin.site.register(Servertype, ServertypeAdmin)
admin.site.register(Attribute)
admin.site.register(Server, ServerAdmin)
admin.site.register(ChangeDelete)
