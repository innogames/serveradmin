from django.conf import settings
from importlib import import_module

class ApiMiddleware(object):
    """Load all api functions which reside in APPNAME.api module."""
    def __init__(self):
        for app in settings.INSTALLED_APPS:
            try:
                import_module(app + '.api')
            except ImportError:
                pass
