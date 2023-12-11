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
        # todo don't check every time...
        try:
            dns_client.get_zone(zone)
        except PowerDNSApiException:
            logging.info(f"Creating new zone {zone}")
            dns_client.create_zone(zone, "Native")

        # todo we have to loop over all domain names not just whole zone..
        # convert our database records to PowerDNS RRSet objects and push via HTTP
        actual = dns_client.get_rrsets(zone, records[0].name)
        expected = db_records_to_pdns_rrsets(records)
        diff = get_changed_records(actual, expected)

        dns_client.create_or_update_rrsets(zone, diff)

        # todo: only send one /notify here in the end to trigger AXFR process?
        dns_client.notify(zone)


def get_changed_records(all_actual: Dict[str, RRSet], all_expected: List[RRSet]) -> List[RRSet]:
    final_changes = []
    for expected in all_expected:
        if expected.type not in all_actual:
            # new record type -> keep!
            final_changes.append(expected)
            continue

        # todo filter out unchanged ones properly
        if all_actual[expected.type] == expected:
            # same contents -> keep!
            logger.info(f"Record {expected.name} {expected.type} are same a:{str(all_actual[expected.type])} r:{str(expected)}")
        else:
            logger.info(f"Record {expected.name} {expected.type} are NOT same a:{str(all_actual[expected.type])} r:{str(expected)}")
            final_changes.append(expected)
        # todo DELETE old ones

    return final_changes


def group_by_zone(records: list) -> Dict[str, list]:
    records_by_zone = {}
    for record in records:
        if record.domain not in records_by_zone:
            records_by_zone[record.domain] = []
        records_by_zone[record.domain].append(record)

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
            content_group_by_type[record.name][record.type] = []

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
        content_group_by_type[record.name][record.type].append(record_content)

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
