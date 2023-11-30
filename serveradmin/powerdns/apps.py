import logging

from django.conf import settings
from django.apps import AppConfig

from serveradmin.powerdns.signals import create_records, delete_records, update_records
from serveradmin.serverdb.signals import post_commit

logger = logging.getLogger(__name__)


class PowerdnsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'serveradmin.powerdns'

    def ready(self):
        if not settings.POWERDNS_API_ENDPOINT:
            logger.info("No PowerDNS API endpoint configured.")
            return

        post_commit.connect(create_records, dispatch_uid="create_dns_records")
        post_commit.connect(delete_records, dispatch_uid="delete_dns_records")
        post_commit.connect(update_records, dispatch_uid="update_dns_records")
