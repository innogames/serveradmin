import logging
import csv

from django.core.management.base import BaseCommand, CommandParser

from adminapi.dataset import Query
from adminapi.exceptions import DatasetError
from serveradmin.powerdns.models import Record
from serveradmin.serverdb.models import Attribute

logger = logging.getLogger(__package__)

# todo: how to configure?
DNS_FIELDS = {
    'CNAME': 'dns_cname',
    'MX': 'dns_mx',
    'TXT': 'dns_txt',
}

IGNORED_DNS_FIELDS = ['SOA', 'NS']


class Command(BaseCommand):
    help = 'Compares and import DNS records of a backup file into the local serveradmin database'

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

        parser.add_argument(
            "--add_to_sa",
            type=bool,
        )

    def handle(self, *args, **options):
        csv_filename = 'ns-2023-12-20.txt'

        # first group by zone->type
        records_by_zone = {}
        with open(csv_filename, mode='r') as file:
            csv_reader = csv.DictReader(file)

            # example record: {'domain': 'example.pl', 'name': 'foo.example.pl', 'type': 'NS', 'content': 'ns2.provider.de', 'ttl': '3600'}
            for record in csv_reader:
                zone = record['domain']
                type = record['type']
                if type in IGNORED_DNS_FIELDS:
                    continue

                if options['zone'] and zone != options['zone']:
                    continue
                if options['type'] and type != options['type']:
                    continue

                if zone not in records_by_zone:
                    records_by_zone[zone] = {}

                identifier = f"{record['name']}-{record['type']}"
                if type == 'MX':
                    record['content'] = f"10 {record['content']}"  # todo correct prio from csv!

                if identifier not in records_by_zone[zone]:
                    records_by_zone[zone][identifier] = record
                    records_by_zone[zone][identifier]['content_list'] = [record['content']]
                else:
                    records_by_zone[zone][identifier]['content_list'].append(record['content'])

        for zone in records_by_zone:

            print(f"Checking zone {zone}:")
            for identifier in records_by_zone[zone]:
                record = records_by_zone[zone][identifier]
                db_records = Record.objects.filter(domain=record['name'], type=record['type']).values_list('content', flat=True)
                db_content_list = sorted([db_record for db_record in db_records])
                backup_str = f"{record['name']} {record['type']} {record['content_list']} ttl:{record['ttl']}"

                if db_content_list and db_content_list == sorted(record['content_list']):
                    # quick return, all good!
                    print(f" ✔️  {identifier}")
                    continue

                if not db_content_list:
                    print(f" ❌  {backup_str} - not in SA")
                else:
                    print(f" ⚠️  {backup_str}: '{db_content_list}' vs '{record['content_list']}'")

                # sync INWX to Serveradmin
                if options['add_to_sa'] and record['type'] in DNS_FIELDS:
                    if '_' in record['name']:
                        print(f"   ❌  {record['name']} is a invalid hostname (contains '_')")
                        continue

                    sa_field = DNS_FIELDS[record['type']]
                    sa_attribute = Attribute.objects.get(attribute_id=sa_field)

                    print(f"   🔧 Adding {sa_field}={record['content_list']} to serveradmin...")
                    query = Query({'hostname': record['name'], 'servertype': 'public_domain'}, [sa_field])
                    if len(query) == 0:
                        print(f"   ➕ added new public_domain for {record['name']}")
                        domain_object = Query().new_object(servertype='public_domain')  # todo : is there some other possible type?
                        domain_object['hostname'] = record['name']
                        domain_object['project'] = 'admin'  # todo: how to get this?
                    else:
                        domain_object = next(iter(query))

                    if sa_attribute.multi:
                        domain_object[sa_field] = record['content_list']  # todo multi/non-multi fields!
                    else:
                        domain_object[sa_field] = record['content_list'][0]

                    try:
                        domain_object.commit()
                    except DatasetError as e:
                        print(f"   ❌  update failed: {e}")
                        continue



