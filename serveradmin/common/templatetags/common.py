"""Serveradmin

Copyright (c) 2021 InnoGames GmbH
"""

from django import template

from adminapi import VERSION

register = template.Library()


@register.filter
def dict_get(value, arg):
    return value.get(arg)


@register.filter
def bootstrap_alert(level_tag):
    """Get Twitter Bootstrap alert CSS class for Django message level

    :param level_tag: Django message.level_tag attribute
    :return: boostrap CSS class e.g. alert-primary
    """

    django_bootstrap = {
        'debug': 'primary',
        'info': 'info',
        'success': 'success',
        'warning': 'warning',
        'error': 'danger',
    }
    return 'alert-' + django_bootstrap[level_tag]


@register.filter
def group(items, number_of_groups):
    """Group items into number of groups

    Takes a countable items and divides it into the desired number of groups.

    :param items:
    :param number_of_groups:
    :return:
    """

    if not items:
        return []

    groups = list()
    step = round(len(items) / number_of_groups)

    # When the amount of columns is zero show at least one
    if step == 0:
        step = 1

    for counter in range(0, len(items), step):
        groups.extend([items[counter : counter + step]])

    return groups


@register.simple_tag()
def get_version():
    """Get current Serveradmin version"""
    return 'v' + '.'.join([str(v) for v in VERSION])
