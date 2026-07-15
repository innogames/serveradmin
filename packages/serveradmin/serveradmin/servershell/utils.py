from django.contrib.staticfiles import finders

from serveradmin.common.utils import serveradmin_apps


def servershell_plugins():
    """Find $app.servershell.plugin.js files from Serveradmin apps

    Scans all apps beginning with serveradmin_ for files that follow the pattern
    $app.servershell.plugin.js and return them. This allows Serveradmin apps to
    extend the Servershell for example with custom commands.

    @return:
    """
    js_files = list()
    for app_name in serveradmin_apps():
        path = f"js/{app_name}.servershell.plugin.js"
        js_file = finders.find(path)
        if js_file:
            js_files.append(path)

    return js_files
