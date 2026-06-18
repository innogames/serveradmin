"""Serveradmin

Copyright (c) 2025 InnoGames GmbH
"""

from typing import Any, Union

from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import escape
from django.utils.safestring import mark_safe

from serveradmin.serverdb.models import Change, Server

register = template.Library()


@register.filter
def hostname(object_id: int) -> Union[str, int]:
    try:
        return Server.objects.get(server_id=object_id).hostname
    except ObjectDoesNotExist:
        return object_id


@register.filter
def get_attribute_changes(change: Change) -> list:
    """Extract attribute changes from a Change object's change_json.

    Returns a list of HTML-safe formatted strings.
    Only works for change_type='change'.
    """
    if change.change_type != 'change':
        return []

    changes_list = []

    for attribute_id, attr_change in change.change_json.items():
        if attribute_id == 'object_id' or not isinstance(attr_change, dict):
            continue

        prefix = f'<strong>{attribute_id}:</strong>'
        action = attr_change.get('action')
        old_val = escape(attr_change.get('old'))
        new_val = escape(attr_change.get('new'))

        if action == 'update':
            if attr_change.get('new') in (None, ''):
                changes_list.append(mark_safe(f'{prefix} <del>{old_val}</del>'))
            else:
                changes_list.append(mark_safe(f'{prefix} <del>{old_val}</del> &rarr; {new_val}'))
        elif action == 'new':
            changes_list.append(mark_safe(f'{prefix} + {new_val}'))
        elif action == 'delete':
            changes_list.append(mark_safe(f'{prefix} <del>{old_val}</del>'))
        elif action == 'multi':
            for val in attr_change.get('remove', []):
                changes_list.append(mark_safe(f'{prefix} <del>{escape(str(val))}</del>'))
            for val in attr_change.get('add', []):
                changes_list.append(mark_safe(f'{prefix} + {escape(str(val))}'))

    return changes_list
