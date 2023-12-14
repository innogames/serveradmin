from django.contrib import admin
from .models import RecordSetting, Record
from .sync.utils import get_dns_zone


class ZoneListFilter(admin.SimpleListFilter):
    title = 'Zone'
    parameter_name = 'zone'

    def lookups(self, request, model_admin):
        # Fetch all unique domain values from records and calculate unique zones
        domains = set(model_admin.model.objects.distinct('domain').values_list('domain', flat=True))
        zones = set(get_dns_zone(domain) for domain in domains)

        return [(zone, zone) for zone in sorted(zones)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(domain__endswith=self.value())
        return queryset


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
        'get_zone',
    ]
    list_filter = [
        'type',
        ZoneListFilter
    ]
    search_fields = [
        'name',
        'content',
        'domain',
    ]

    @admin.display(description='Zone')
    def get_zone(self, obj: Record) -> str:
        return obj.get_zone()

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(Record, RecordAdmin)
admin.site.register(RecordSetting, RecordSettingAdmin)
