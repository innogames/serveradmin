from django.apps import AppConfig
from django.conf import settings
from django.dispatch import Signal

from serveradmin.serverdb.query_committer import post_commit


class PowerdnsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'serveradmin.powerdns'

    def ready(self):
        if settings.PDNS_ENABLE:
            from . import signals

            # Connect signals here instead of using the @receiver decorator to
            # avoid accidental connection of signals when importing the signals
            # module (e.g. in unit tests).
            Signal.connect(post_commit, signals.create_domains)
            Signal.connect(post_commit, signals.update_domains)
            Signal.connect(post_commit, signals.delete_domains)
