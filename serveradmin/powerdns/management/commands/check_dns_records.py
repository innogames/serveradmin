import logging
import csv

from django.core.management.base import BaseCommand, CommandParser

from serveradmin.powerdns.models import Record

logger = logging.getLogger(__package__)


class Command(BaseCommand):
    help = 'Check DNS records of a backup file with the local powerdns'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--zone",
            type=str,
            help="Limit check to given zone, like example.com",
        )
        parser.add_argument(
            "--type",
            type=str,
            help="Limit check to given DNS record type, like A or NS",
        )
        parser.add_argument(
            "--file",
            type=str,
        )

    def handle(self, *args, **options):
        csv_filename = 'ns-2023-12-20.txt'

        # first group by zones
        records_by_zone = {}
        with open(csv_filename, mode='r') as file:
            csv_reader = csv.DictReader(file)

            # example record: {'domain': 'example.pl', 'name': 'foo.example.pl', 'type': 'NS', 'content': 'ns2.provider.de', 'ttl': '3600'}
            for record in csv_reader:
                zone = record['domain']
                type = record['type']
                #if type in ['SOA', 'NS']:
                #    # todo: ignore for now
                #    continue

                if options['zone'] and zone != options['zone']:
                    continue
                if options['type'] and type != options['type']:
                    continue

                if zone not in records_by_zone:
                    records_by_zone[zone] = []
                records_by_zone[zone].append(record)

        for zone in records_by_zone:
            print(f"Checking zone {zone} with {len(records_by_zone[zone])} records...")
            for record in records_by_zone[zone]:
                db_record = Record.objects.filter(domain=record['name'], type=record['type']).first()
                backup_str = f"{record['name']} {record['type']} {record['content']} ttl:{record['ttl']}"
                if not db_record:
                    print(f" ❌ {backup_str}")
                    continue
                if db_record.content != record['content']:
                    print(f" ⚠️ {backup_str} vs {db_record.content}")
                    continue

                print(f" ✔️ {backup_str}")
