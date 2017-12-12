import importlib
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class ApiMiddleware(object):
    """Load all api functions which reside in APPNAME.api module."""

    def __init__(self):
        for app in settings.INSTALLED_APPS:
            api = importlib.util.find_spec(app + '.api')
            if api is None:
                logger.debug('No api calls found for module {}'.format(app))
            else:
                try:
                    importlib.import_module(app + '.api')
                except ImportError as e:
                    logger.error(
                        'Loading api calls for module {} failed: {}'
                        .format(app, e)
                    )
                    raise
                else:
                    logger.debug(
                        'Successfuly loaded api calls for module {}'
                        .format(app)
                    )
