import importlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class HooksMiddleware(object):
    """Load all hooks which reside in APPNAME.hooks module"""

    def __init__(self):
        for app in settings.INSTALLED_APPS:
            hook = importlib.util.find_spec(app + '.hooks')
            if hook is None:
                logger.debug('No hooks found for module {}'.format(app))
                continue

            try:
                importlib.import_module(app + '.hooks')
            except ImportError as e:
                logger.error(
                    'Loading hooks for module {} failed: {}'.format(app, e)
                )
                raise

            logger.debug('Successfully loaded hooks for module {}'.format(app))
