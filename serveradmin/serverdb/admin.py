from django.contrib import admin

from serveradmin.serverdb.models import (
        Project,
        ServerType,
        Attribute,
        Segment,
        ChangeDelete,
    )

class AttributeAdmin(admin.ModelAdmin):
    fields = ('hovertext', 'help_link', 'group', 'readonly')

admin.site.register(Project)
admin.site.register(ServerType)
admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Segment)
admin.site.register(ChangeDelete)
