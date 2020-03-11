"""Serveradmin

Copyright (c) 2020 InnoGames GmbH
"""

from django import template
from django.core.exceptions import ObjectDoesNotExist

from serveradmin.serverdb.models import Server

register = template.Library()


@register.filter
def hostname(object_id):
    try:
        return Server.objects.get(server_id=object_id).hostname
    except ObjectDoesNotExist:
        return object_id
