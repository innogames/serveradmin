from django.contrib import admin

from serveradmin.serverdb.models import (
    Project,
    ServerType,
    Attribute,
    ServerTypeAttribute,
    Segment,
    ServerObject,
    ServerHostnameAttribute,
    ServerStringAttribute,
    ChangeDelete,
)

class ServerTypeAttributeInline(admin.TabularInline):
    model = ServerTypeAttribute

class ServerTypeAdmin(admin.ModelAdmin):
    inlines = (
        ServerTypeAttributeInline,
    )

class ServerHostnameAttributeInline(admin.TabularInline):
    model = ServerHostnameAttribute
    fk_name = 'server'

class ServerStringAttributeInline(admin.TabularInline):
    model = ServerStringAttribute

class ServerObjectAdmin(admin.ModelAdmin):
    inlines = (
        ServerHostnameAttributeInline,
        ServerStringAttributeInline,
    )

admin.site.register(Project)
admin.site.register(ServerType, ServerTypeAdmin)
admin.site.register(Attribute)
admin.site.register(Segment)
admin.site.register(ServerObject, ServerObjectAdmin)
admin.site.register(ChangeDelete)
