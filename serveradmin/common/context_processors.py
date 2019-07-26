"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

from django.conf import settings


def base(request):
    return {'MENU_TEMPLATES': settings.MENU_TEMPLATES}
