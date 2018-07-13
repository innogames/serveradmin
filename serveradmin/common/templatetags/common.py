"""Serveradmin

Copyright (c) 2018 InnoGames GmbH
"""

import socket

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def logo():
    if getattr(settings, 'IS_SECONDARY', False):
        return settings.STATIC_URL + 'logo_innogames_bigbulb_120_warn.png'
    else:
        return settings.STATIC_URL + 'logo_innogames_bigbulb_120.png'


@register.filter
def dict_get(value, arg):
    return value.get(arg)


@register.simple_tag
def gethostname():
    return socket.gethostname()
