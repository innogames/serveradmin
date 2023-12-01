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


class RecordAdmin(admin.ModelAdmin):
    """This is the "records" VIEW. Show it readonly in the admin interface
    """

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
    search_fields = [
        'name',
        'content',
        'domain',
    ]

    # todo is there a cleaner way to block modification on the VIEW?
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(Record, RecordAdmin)
admin.site.register(RecordSetting, RecordSettingAdmin)
