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
