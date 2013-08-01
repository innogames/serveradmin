from django.contrib import admin

from serveradmin.serverdb.models import Segment, SegmentUsage, ChangeDelete

admin.site.register(Segment)
admin.site.register(SegmentUsage)
admin.site.register(ChangeDelete)
