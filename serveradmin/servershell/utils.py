from django.apps import apps
from django.contrib.staticfiles import finders


def servershell_plugins():
    """Find $app.servershell.plugin.js files from Serveradmin apps

    Scans all apps beginning with serveradmin_ for files that follow the pattern
    $app.servershell.plugin.js and return them. This allows Serveradmin apps to
    extend the Servershell for example with custom commands.

    @return:
    """
    js_files = list()
    app_names = [app.name for app in apps.get_app_configs() if app.name.startswith("serveradmin_")]
    for app_name in app_names:
        path = f"js/{app_name}.servershell.plugin.js"
        js_file = finders.find(path)
        if js_file:
            js_files.append(path)

    return js_files
