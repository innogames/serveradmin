"""Serveradmin - Task queue admin

Copyright (c) 2026 InnoGames GmbH
"""

import json
from typing import Any

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now

from serveradmin.taskqueue import queue
from serveradmin.taskqueue.models import Task


@admin.action(description='Retry selected finished tasks (reset attempts)')
def retry_tasks(modeladmin, request, queryset) -> None:
    count = queue.retry(queryset)
    modeladmin.message_user(
        request, '{} task(s) re-queued.'.format(count), messages.SUCCESS
    )


@admin.action(description='Cancel selected pending tasks')
def cancel_tasks(modeladmin, request, queryset) -> None:
    count = queue.cancel(queryset)
    modeladmin.message_user(
        request, '{} task(s) cancelled.'.format(count), messages.SUCCESS
    )


@admin.action(description='Release lease of selected running tasks')
def release_lease(modeladmin, request, queryset) -> None:
    count = queryset.filter(state=Task.State.RUNNING).update(locked_until=now())
    modeladmin.message_user(
        request, '{} lease(s) released.'.format(count), messages.SUCCESS
    )


def _pre(value: Any) -> str:
    return format_html(
        '<pre style="white-space: pre-wrap">{}</pre>',
        json.dumps(value, indent=2, sort_keys=True, default=str),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'task_type',
        'state',
        'commit_link',
        'attempts',
        'max_attempts',
        'run_after',
        'locked_by',
        'created_at',
        'finished_at',
        'short_error',
    ]
    list_filter = ['state', 'task_type']
    search_fields = ['=id', '=commit__id', 'last_error', 'locked_by']
    date_hierarchy = 'created_at'
    ordering = ['-id']
    list_select_related = ['commit']
    show_full_result_count = False
    actions = [retry_tasks, cancel_tasks, release_lease]
    readonly_fields = [
        'id',
        'task_type',
        'commit_link',
        'state',
        'attempts',
        'max_attempts',
        'run_after',
        'locked_by',
        'locked_at',
        'locked_until',
        'created_at',
        'finished_at',
        'last_error',
        'payload_pretty',
        'result_pretty',
    ]
    fields = readonly_fields

    def has_add_permission(self, request) -> bool:
        return False

    @admin.display(description='Commit', ordering='commit_id')
    def commit_link(self, obj: Task) -> str:
        if obj.commit_id is None:
            return '-'
        url = reverse('serverdb_changes') + '?commit_id={}'.format(obj.commit_id)
        return format_html('<a href="{}">{}</a>', url, obj.commit_id)

    @admin.display(description='Error')
    def short_error(self, obj: Task) -> str:
        if not obj.last_error:
            return ''
        last_line = obj.last_error.strip().splitlines()[-1]
        return last_line[:80]

    @admin.display(description='Payload')
    def payload_pretty(self, obj: Task) -> str:
        return _pre(obj.payload)

    @admin.display(description='Result')
    def result_pretty(self, obj: Task) -> str:
        return _pre(obj.result)
