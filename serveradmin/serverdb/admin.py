from django.contrib import admin

from serveradmin.serverdb.models import (
    Project,
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ServerRelationAttribute,
    ServerStringAttribute,
    ChangeDelete,
)


class ServertypeAttributeInline(admin.TabularInline):
    model = ServertypeAttribute


class ServertypeAdmin(admin.ModelAdmin):
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


admin.site.register(Project)
admin.site.register(Servertype, ServertypeAdmin)
admin.site.register(Attribute)
admin.site.register(Server, ServerAdmin)
admin.site.register(ChangeDelete)
