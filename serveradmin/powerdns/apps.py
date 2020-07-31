from django.apps import AppConfig


class PowerdnsConfig(AppConfig):
    name = 'serveradmin.powerdns'

    def ready(self):
        import serveradmin.powerdns.signals.domains # noqa