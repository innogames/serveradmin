from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'serveradmin.api'
    verbose_name = 'Api'

    def ready(self):
        import serveradmin.api.api  # noqa
