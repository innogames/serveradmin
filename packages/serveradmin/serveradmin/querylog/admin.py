"""Serveradmin - Ad-hoc Query Logging

Copyright (c) 2026 InnoGames GmbH
"""

from django.contrib import admin

from serveradmin.querylog.models import QueryLog, QueryLoggingRule


@admin.register(QueryLoggingRule)
class QueryLoggingRuleAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'user', 'is_active', 'enabled_until',
        'note', 'created_by', 'created_at',
    ]
    list_filter = ['is_active', 'application']
    search_fields = ['application__name', 'user__username', 'note']
    autocomplete_fields = ['application', 'user']
    readonly_fields = ['created_at', 'created_by']
    list_select_related = ['application', 'user', 'created_by']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'source', 'application', 'user',
        'duration_ms', 'num_results', 'short_query_text',
    ]
    list_filter = ['source', 'application', 'user']
    search_fields = ['query_text']
    date_hierarchy = 'created_at'
    list_select_related = ['application', 'user', 'rule']

    # This table has no automated retention/cleanup (see the plan this
    # feature was built from), so it can grow unbounded. Avoid a slow
    # exact COUNT(*) on every paginated list view - same motivation as
    # the custom NoCountPaginator used for the (much larger) ChangeCommit
    # log in serverdb/views.py.
    show_full_result_count = False

    @admin.display(description='Query')
    def short_query_text(self, obj):
        if len(obj.query_text) <= 120:
            return obj.query_text
        return obj.query_text[:117] + '...'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # has_delete_permission is left at the ModelAdmin default (True):
    # deleting old rows via the admin is the only housekeeping mechanism
    # since there is no automated retention job in this version.
