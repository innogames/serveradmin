from django.apps import AppConfig
from django.conf import settings


class PowerdnsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'serveradmin.powerdns'

    def ready(self):
        if settings.PDNS_ENABLE:
            from . import signals # noqa
