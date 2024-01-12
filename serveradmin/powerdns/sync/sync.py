import logging
import time
from typing import List, Dict

from serveradmin.powerdns.sync.client import PowerDNSApiClient
from serveradmin.powerdns.sync.objects import RecordContent, RRSet
from serveradmin.powerdns.sync.utils import ensure_canonical, quote_string

logger = logging.getLogger(__package__)

# todo access to ClouDNS
# todo base setup of Zone Transfer
# todo move to serveradmin_extras
# todo add MX priority to INWX backup
def sync_records(records: list, delete_unknown_in_zones: bool = True, sync_whole_zone: bool = False):
    if not records:
        return

    dns_client = PowerDNSApiClient()
    changed = 0
    start_time = time.time()

    # handle each domain separately and push all touched records to PowerDNS
    for zone, zone_records in group_by_zone(records).items():
        dns_client.ensure_zone_exists(zone)

        # first we have to fetch all relevant existing records from powerdns to check for diff
        # in most cases we only need to fetch the records for the domain we are
        # currently syncing instead of the whole zone
        if sync_whole_zone:
            actual = dns_client.get_rrsets(zone)
        else:
            actual = {}
            for domain_name in set([record.name for record in zone_records]):
                actual[ensure_canonical(domain_name)] = dns_client.get_rrsets(zone, domain_name).get(
                    ensure_canonical(domain_name), []
                )

        # convert our database records to PowerDNS RRSet objects and push via HTTP
        expected = db_records_to_pdns_rrsets(zone, zone_records)
        diff = get_changed_records(actual, expected, delete_unknown_in_zones)
        if not diff:
            continue

        dns_client.create_or_update_rrsets(zone, diff)
        changed += len(diff)

        # todo: only send one /notify here in the end (IF there were changes) to trigger AXFR process only once?
        #dns_client.notify(zone)

    logger.info(
        f"DNS sync took {round(time.time() - start_time, 2)}s. "
        f"{len(records)} records. {changed} changes."
    )


def get_changed_records(all_actual: Dict[str, Dict[str, RRSet]], all_expected: List[RRSet],
                        delete_unknown_in_zones: bool) -> List[RRSet]:
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
            logger.info(
                f"Record {expected.name} {expected.type} are "
                f"NOT same {str(all_actual[expected.name][expected.type])} != {str(expected)}"
            )
            final_changes.append(expected)

        del all_actual[expected.name][expected.type]

        # no changes anymore for this domain!
        if not all_actual[expected.name]:
            del all_actual[expected.name]

    if delete_unknown_in_zones:
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
                # there might be a case where we have a CNAME and a A record for the same name in INWX
                continue

            final_rrsets.append(rrset)

    return final_rrsets
