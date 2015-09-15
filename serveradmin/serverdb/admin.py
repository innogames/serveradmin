from django.contrib import admin

from serveradmin.serverdb.models import (
        Attribute,
        Project,
        Segment,
        SegmentUsage,
        ChangeDelete,
    )

class AttributeAdmin(admin.ModelAdmin):
    fields = ('hovertext', 'help_link', 'group', 'readonly')

admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Project)
admin.site.register(Segment)
admin.site.register(SegmentUsage)
admin.site.register(ChangeDelete)
