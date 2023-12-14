import logging
from typing import List, Dict

from serveradmin.powerdns.sync.client import PowerDNSApiClient, PowerDNSApiException
from serveradmin.powerdns.sync.objects import RecordContent, RRSet
from serveradmin.powerdns.sync.utils import ensure_canonical, quote_string

logger = logging.getLogger(__package__)


def sync_records(records: list):
    dns_client = PowerDNSApiClient()

    # handle each domain separately and push all touched records to PowerDNS
    for zone, records in group_by_zone(records).items():
        if not zone:
            # todo: valid case? I got this while doing a full sync
            continue

        # todo don't check every time...maybe just in case of 404 of client.get_rrsets?
        try:
            dns_client.get_zone(zone)
        except PowerDNSApiException:
            logger.info(f"Creating new zone {zone}")
            dns_client.create_zone(zone, "Primary")

        # first we have to fetch all relevant existing records from powerdns to check for diff
        # in most cases we only need to fetch the records for the domain we are
        # currently syncing instead of the whole zone
        domain_names = set([record.name for record in records])
        domain_filter = ''
        if len(domain_names) == 1:
            domain_filter = domain_names.pop()
        actual = dns_client.get_rrsets(zone, domain_filter)

        # convert our database records to PowerDNS RRSet objects and push via HTTP
        expected = db_records_to_pdns_rrsets(records)
        diff = get_changed_records(actual, expected)
        if not diff:
            continue

        dns_client.create_or_update_rrsets(zone, diff)

        # todo: only send one /notify here in the end (IF there were changes) to trigger AXFR process?
        dns_client.notify(zone)


def get_changed_records(all_actual: Dict[str, Dict[str, RRSet]], all_expected: List[RRSet]) -> List[RRSet]:
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

        # todo: we don't care so far, most likely powerdns config will take care of this
        if 'SOA' in all_actual[expected.name]:
            del all_actual[expected.name]['SOA']

        # no changes anymore for this domain!
        if not all_actual[expected.name]:
            del all_actual[expected.name]

    # todo DELETE old ones
    if all_actual:
        logger.info(f"Found some old records: {all_actual}")

    return final_changes


def group_by_zone(records: list) -> Dict[str, list]:
    records_by_zone = {}
    for record in records:
        zone = record.get_zone()
        if zone not in records_by_zone:
            records_by_zone[zone] = []
        records_by_zone[zone].append(record)

    return records_by_zone


def db_records_to_pdns_rrsets(records: list) -> List[RRSet]:
    """Convert database records to PowerDNS RRSet objects
    This groups the records by name and type and creates a RRSet object for each
    """
    content_group_by_type = {}

    for record in records:
        if record.name not in content_group_by_type:
            content_group_by_type[record.name] = {}
        if record.type not in content_group_by_type[record.name]:
            content_group_by_type[record.name][record.type] = set()

        # some special handling for certain record types
        if record.type in ['PTR', 'CNAME']:
            record.content = ensure_canonical(record.content)
        elif record.type == 'TXT':
            # TXT records need to be quoted via powerdns API
            record.content = quote_string(record.content)
        elif record.type == 'MX':
            # todo which prio?
            record.content = f"10 {ensure_canonical(record.content)}"

        record_content = RecordContent(record.content)
        content_group_by_type[record.name][record.type].add(record_content)

    rrsets = []
    for name, types in content_group_by_type.items():
        for type, contents in types.items():
            rrset = RRSet()
            rrset.type = type
            rrset.name = ensure_canonical(name)
            rrset.ttl = get_ttl()
            rrset.records = contents
            rrsets.append(rrset)

    return rrsets


def get_ttl():
    """todo: somehow configurable via RecordsSettings?"""
    return 300
