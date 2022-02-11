from django.apps import AppConfig


class PowerdnsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'serveradmin.powerdns'

    def ready(self):
        from . import signals # noqa
