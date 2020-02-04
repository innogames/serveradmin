"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

import socket

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def logo():
    return settings.STATIC_URL + settings.LOGO_FILENAME


@register.filter
def dict_get(value, arg):
    return value.get(arg)


@register.simple_tag
def gethostname():
    return socket.gethostname()


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
