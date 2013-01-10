from django.contrib import admin

from serveradmin.iprange.models import IPRange, Route, SegmentRoute

admin.site.register(IPRange)
admin.site.register(Route)
admin.site.register(SegmentRoute)
