import logging
import time
from django.core.management.base import BaseCommand, CommandParser

from serveradmin.powerdns.sync.sync import sync_records
from serveradmin.powerdns.models import Record


logger = logging.getLogger(__package__)


class Command(BaseCommand):
    help = 'Sync DNS records from Serveradmin with the configured PowerDNS'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--domain",
            type=str,
            help="Limit sync to given domain, like eu.example.com or example.com",
        )

    def handle(self, *args, **options):
        records = Record.objects

        if options['domain']:
            records = records.filter(domain__endswith=options['domain'])
        records = records.all()

        start = time.time()

        logger.info(f"Start syncing {len(records)} records...")
        sync_records(records)
        logger.info(f"Sync took {round(time.time() - start, 2)}s for {len(records)} records")
