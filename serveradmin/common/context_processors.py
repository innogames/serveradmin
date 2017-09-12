from glob import iglob

from django.apps import apps
from django.core.cache import cache


def base(request):
    return {'MENU_TEMPLATES': _get_menu_templates()}


def _get_menu_templates():
    """Get menu template names -> tuple

    Try to automatically find menu templates with the naming scheme
    <app>/menu.html in the apps and in the global settings.MENU_TEMPLATES
    tuple and return a tuple of them.
    """

    menu_templates = cache.get('menu_templates')
    if menu_templates:
        return menu_templates

    menu_templates = []
    for app in apps.get_app_configs():
        for path in iglob('{}/templates/*/menu.html'.format(app.path)):
            menu_templates.append('/'.join(path.rsplit('/', 2)[-2:]))

    cache.set('menu_templates', menu_templates)
    return tuple(menu_templates)
