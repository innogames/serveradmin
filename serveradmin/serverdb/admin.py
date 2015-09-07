from django.contrib import admin

from serveradmin.serverdb.models import (
        Attribute,
        Department,
        Segment,
        SegmentUsage,
        ChangeDelete,
    )

class AttributeAdmin(admin.ModelAdmin):
    fields = ('hovertext', 'help_link', 'group')

admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Department)
admin.site.register(Segment)
admin.site.register(SegmentUsage)
admin.site.register(ChangeDelete)
