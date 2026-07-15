"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

import functools
import os

from django.apps import apps
from django.conf import settings

from serveradmin.common.utils import serveradmin_apps


def base(request):
    return {'MENU_TEMPLATES': list(settings.MENU_TEMPLATES) + _app_menu_templates()}


@functools.lru_cache(maxsize=1)
def _app_menu_templates():
    """Discover menu.html templates shipped by optional serveradmin_* apps

    Following the serveradmin_ naming convention, any such app can add entries
    to the navigation of base.html simply by shipping one or more menu.html
    templates in its templates/ directory - no local_settings.py editing
    required. A single app may ship several (e.g. serveradmin_extras provides
    templates/nagios/menu.html, templates/networking/menu.html, ...); every
    menu.html found at any depth is registered by its path relative to the
    templates/ directory, which is exactly the name {% include %} expects.

    The result is memoized because the set of installed apps and their
    templates is fixed after startup.

    @return: sorted list of template names
    """
    paths_by_app = {app.name: app.path for app in apps.get_app_configs()}

    templates = []
    for app_name in serveradmin_apps():
        templates_dir = os.path.join(paths_by_app[app_name], 'templates')
        for root, _dirs, files in os.walk(templates_dir):
            if 'menu.html' not in files:
                continue
            full = os.path.join(root, 'menu.html')
            name = os.path.relpath(full, templates_dir).replace(os.sep, '/')
            templates.append(name)

    return sorted(templates)
