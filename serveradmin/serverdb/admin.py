from django.contrib import admin

from serveradmin.serverdb.models import Segment, SegmentUsage

admin.site.register(Segment)
admin.site.register(SegmentUsage)
