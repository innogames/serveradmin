"""Serveradmin - Ad-hoc Query Logging

Copyright (c) 2026 InnoGames GmbH
"""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple

from serveradmin.querylog.models import QueryLog, QueryLoggingRule
from serveradmin.serverdb.models import Attribute


def _attribute_choices():
    """(value, label) choices for the trigger_attributes widget

    Computed on demand (called from QueryLoggingRuleForm.__init__, not at
    class-definition time) so newly added Attribute rows show up without
    restarting the process, and so importing this module never queries
    the DB.
    """
    real_ids = Attribute.objects.values_list('attribute_id', flat=True)
    all_ids = set(real_ids) | set(Attribute.specials.keys())
    return sorted((attribute_id, attribute_id) for attribute_id in all_ids)


class QueryLoggingRuleForm(forms.ModelForm):
    trigger_attributes = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=FilteredSelectMultiple('attributes', is_stacked=False),
    )

    class Meta:
        model = QueryLoggingRule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trigger_attributes'].choices = _attribute_choices()


@admin.register(QueryLoggingRule)
class QueryLoggingRuleAdmin(admin.ModelAdmin):
    form = QueryLoggingRuleForm
    list_display = [
        'application', 'user', 'is_active', 'enabled_until',
        'short_trigger_query', 'short_trigger_attributes', 'note',
        'created_by', 'created_at',
    ]
    list_filter = ['is_active', 'application']
    search_fields = ['application__name', 'user__username', 'note']
    autocomplete_fields = ['application', 'user']
    readonly_fields = ['created_at', 'created_by']
    list_select_related = ['application', 'user', 'created_by']

    @admin.display(description='Trigger query')
    def short_trigger_query(self, obj):
        if len(obj.trigger_query) <= 60:
            return obj.trigger_query
        return obj.trigger_query[:57] + '...'

    @admin.display(description='Trigger attributes')
    def short_trigger_attributes(self, obj):
        joined = ', '.join(obj.trigger_attributes)
        if len(joined) <= 60:
            return joined
        return joined[:57] + '...'

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
