"""Serveradmin

Copyright (c) 2018 InnoGames GmbH
"""

from django.conf import settings


def base(request):
    return {'MENU_TEMPLATES': settings.MENU_TEMPLATES}
