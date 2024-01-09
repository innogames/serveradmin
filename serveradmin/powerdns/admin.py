from django.contrib import admin
from .models import RecordSetting, Record
from .sync.sync import sync_records
from .sync.utils import get_dns_zone
from .view_sql import ViewSQL


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


@admin.action(description="Sync with Powerdns")
def sync_with_powerdns(modeladmin, request, queryset):
    records = Record.objects.all()
    sync_records(records)


@admin.action(description="Update SQL View")
def update_view(modeladmin, request, queryset):
    ViewSQL.update_view_schema()


class RecordSettingAdmin(admin.ModelAdmin):
    list_display = [
        'servertype',
        'record_type',
        'source_value_field',
        'domain_field',
        'ttl',
    ]
    ordering = ('record_type',)
    actions = [sync_with_powerdns, update_view]

    @admin.display(description='Source Attribute')
    def source_value_field(self, obj: Record) -> str:
        if obj.source_value:
            return obj.source_value
        else:
            return obj.source_value_special

    @admin.display(description='Domain attribute')
    def domain_field(self, obj: Record) -> str:
        if obj.domain:
            return obj.domain
        else:
            return 'hostname (default)'


class RecordAdmin(admin.ModelAdmin):
    """This is the "records" VIEW. Show it readonly in the admin interface
    """

    list_display = [
        'object_ids',
        'name',
        'type',
        'content',
        'domain',
        'get_zone',
        'ttl',
    ]
    list_filter = [
        'type',
        ZoneListFilter,
        'ttl',
    ]
    search_fields = [
        'name',
        'content',
        'domain',
    ]
    show_full_result_count = False  # prevent slow SELECT COUNT(*) on the View

    @admin.display(description='Zone')
    def get_zone(self, obj: Record) -> str:
        return obj.get_zone()

    def has_change_permission(self, request, obj=None):
        # we're in the read-only VIEW -> block any changes
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(Record, RecordAdmin)
admin.site.register(RecordSetting, RecordSettingAdmin)
