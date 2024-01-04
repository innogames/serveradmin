import logging
from typing import List, Dict

from serveradmin.powerdns.sync.client import PowerDNSApiClient
from serveradmin.powerdns.sync.objects import RecordContent, RRSet
from serveradmin.powerdns.sync.utils import ensure_canonical, quote_string

logger = logging.getLogger(__package__)


# todo fix renaming domain should drop old entries
def sync_records(records: list):
    dns_client = PowerDNSApiClient()

    # handle each domain separately and push all touched records to PowerDNS
    for zone, records in group_by_zone(records).items():
        dns_client.ensure_zone_exists(zone)

        # first we have to fetch all relevant existing records from powerdns to check for diff
        # in most cases we only need to fetch the records for the domain we are
        # currently syncing instead of the whole zone
        domain_names = set([record.name for record in records])
        domain_filter = ''
        if len(domain_names) == 1:
            # todo: find a smarter way to do fetch only relevant records without fetching the whole zone
            domain_filter = domain_names.pop()
        actual = dns_client.get_rrsets(zone, domain_filter)

        # convert our database records to PowerDNS RRSet objects and push via HTTP
        expected = db_records_to_pdns_rrsets(zone, records)
        diff = get_changed_records(actual, expected)
        if not diff:
            continue

        dns_client.create_or_update_rrsets(zone, diff)

        # todo: only send one /notify here in the end (IF there were changes) to trigger AXFR process only once?
        dns_client.notify(zone)


# todo: this is a bit hacky, maybe we can confugure it somewhere else, as we have to set the NS records for all zones
def get_ns_records(zone: str) -> RRSet:
    servers = ['ns1.example.com', 'ns2.example.com']  # todo jus some dummy test

    rrset = RRSet(zone, 'NS', 3600)

    for server in servers:
        rrset.records.add(RecordContent(ensure_canonical(server)))

    return rrset


def get_changed_records(all_actual: Dict[str, Dict[str, RRSet]], all_expected: List[RRSet]) -> List[RRSet]:
    """
    Compare the actual records from PowerDNS with the expected records from the database
    The list contains entries with changetype "REPLACE" with all entries to delete or update.
    And "DELETE" for all unknown ones to wipe
    """
    final_changes = []
    for expected in all_expected:
        if expected.name not in all_actual or expected.type not in all_actual[expected.name]:
            # new record type -> keep!
            final_changes.append(expected)
            continue

        if all_actual[expected.name][expected.type] != expected:
            logger.info(f"Record {expected.name} {expected.type} are NOT same {str(all_actual[expected.name][expected.type])} != {str(expected)}")
            final_changes.append(expected)

        del all_actual[expected.name][expected.type]

        # no changes anymore for this domain!
        if not all_actual[expected.name]:
            del all_actual[expected.name]

    # delete all unknown ones!
    for name_to_delete in all_actual:
        for type_to_delete in all_actual[name_to_delete]:
            rrset = RRSet(name_to_delete, type_to_delete, None)
            rrset.changetype = 'DELETE'

            # we prepend all DELETEs to make sure we don't get conflicts with other REPLACE in the same request
            final_changes.insert(0, rrset)
            logger.info(f"Record {rrset} is old, deleting")

    return final_changes


def group_by_zone(records: list) -> Dict[str, list]:
    records_by_zone = {}
    for record in records:
        zone = record.get_zone()
        if zone not in records_by_zone:
            records_by_zone[zone] = []
        records_by_zone[zone].append(record)

    return records_by_zone


def db_records_to_pdns_rrsets(zone: str, records: list) -> List[RRSet]:
    """Convert database records to PowerDNS RRSet objects
    This function groups the records by name and type and creates a flat list of RRSet
    """
    rrsets_group_by_type = {}

    for record in records:
        if record.name not in rrsets_group_by_type:
            rrsets_group_by_type[record.name] = {}
        if record.type not in rrsets_group_by_type[record.name]:
            rrset = RRSet(record.name, record.type, record.ttl)
            rrsets_group_by_type[record.name][record.type] = rrset

        # some special handling for certain record types
        if record.type in ['PTR', 'CNAME', 'MX']:
            # we need the trailing "."
            record.content = ensure_canonical(record.content)
        elif record.type == 'TXT':
            # TXT records need to be quoted via powerdns API
            record.content = quote_string(record.content)

        record_content = RecordContent(record.content)
        rrsets_group_by_type[record.name][record.type].records.add(record_content)

    final_rrsets = []
    for name, types in rrsets_group_by_type.items():
        for type, rrset in types.items():
            if "CNAME" in types and type != "CNAME":
                # if there is a CNAME set, ignore all other records for this name
                continue

            final_rrsets.append(rrset)

    final_rrsets.append(get_ns_records(zone))

    return final_rrsets
