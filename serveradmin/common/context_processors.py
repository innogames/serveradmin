from os.path import exists, abspath
from glob import iglob

from django.conf import settings
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
    if hasattr(settings, 'MENU_TEMPLATES'):
        menu_templates.extend(settings.MENU_TEMPLATES)

    for app in settings.INSTALLED_APPS:
        app_name = app.split('.').pop()
        patterns = (
            '{}/{}/templates/*/menu.html'.format(settings.ROOT_DIR, app_name),
            '{}/{}/templates/*/menu.html'.format(
                abspath(settings.ROOT_DIR + '/../'), app_name
            )
        )
        for pattern in patterns:
            for template_path in iglob(pattern):            
                template_name = '/'.join(template_path.split('/')[-2:])
                if template_name not in menu_templates:
                    menu_templates.append(template_name)

    cache.set('menu_templates', menu_templates)
    return tuple(menu_templates)
