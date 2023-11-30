from django.contrib import admin
from .models import RecordSetting, Record


class RecordSettingAdmin(admin.ModelAdmin):
    list_display = [
        'servertype',
        'record_type',
        'source_value',
        'source_value_special',
        'domain',
    ]


admin.site.register(RecordSetting, RecordSettingAdmin)


# show VIEWs
class RecordAdmin(admin.ModelAdmin):
    list_display = [
        'object_id',
        'name',
        'type',
        'content',
        'domain',
    ]
    list_filter = [
        'type',
        'domain',
    ]


admin.site.register(Record, RecordAdmin)
