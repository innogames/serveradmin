import logging
import time
from django.core.management.base import BaseCommand

from serveradmin.powerdns.sync import sync_records
from serveradmin.powerdns.models import Record


logger = logging.getLogger(__package__)


class Command(BaseCommand):
    help = 'Sync DNS records from serveradmin with the configured PowerDNS'

    def handle(self, *args, **options):
        records = Record.objects
        # todo add more filters here
        records = records.filter(type='MX')

        records = records.all()

        start = time.time()
        sync_records(records)
        logger.info(f"Sync took {time.time() - start}s for {len(records)} records")
