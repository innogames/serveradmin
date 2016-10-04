from django.conf import settings
from importlib import import_module


class HooksMiddleware(object):
    """Load all hooks which reside in APPNAME.hooks module"""

    def __init__(self):
        for app in settings.INSTALLED_APPS:
            try:
                import_module(app + '.hooks')
            except ImportError:
                pass
