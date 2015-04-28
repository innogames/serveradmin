from django.contrib import admin

from serveradmin.serverdb.models import (Attribute, Segment, SegmentUsage,
                                       ChangeDelete)

class AttributeAdmin(admin.ModelAdmin):
    fields = ('hovertext', 'group')

admin.site.register(Attribute, AttributeAdmin)
admin.site.register(Segment)
admin.site.register(SegmentUsage)
admin.site.register(ChangeDelete)
