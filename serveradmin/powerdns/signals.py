import logging

from serveradmin.powerdns.http_client.utils import ensure_trailing_dot, quote_string
from serveradmin.common.utils import profile
from serveradmin.powerdns.http_client.client import PowerDNSApiClient
from serveradmin.powerdns.http_client.objects import RRSet, RecordContent, get_ttl

logger = logging.getLogger(__package__)


@profile
def create_records(sender, **kwargs):
    """Create PowerDNS domain for newly created objects
    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['created']:
        return

    for new_object in kwargs['created']:
        servertype = new_object['servertype']

        logger.error(f"matze to create {servertype} {new_object}")


@profile
def delete_records(sender, **kwargs):
    """Delete PowerDNS domain for deleted objects
    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['deleted']:
        return
    from serveradmin.powerdns.models import Record

    object_ids = kwargs['deleted']
    records = Record.objects.filter(object_id__in=object_ids).all()
    logger.error(f"matze to delete {records}")


@profile
def update_records(sender, **kwargs):
    """Update PowerDNS domain when changed
    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['changed']:
        return

    dns_client = PowerDNSApiClient()

    # todo: just a test
    # try:
    #    create_zone_result = dns_client.create_zone("ip6.arpa.", "Native")
    #    logger.info("Create Zone Result:", create_zone_result)
    # except PowerDNSApiException as e:
    #    logger.info(f"An error occurred: {e}")

    # Is any of the updated objects mapped to a PowerDNS domain?
    from serveradmin.powerdns.models import Record
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    records = Record.objects.filter(object_id__in=object_ids).all()
    logger.error(f"matze records {records}")
    if not records:
        # nothing DNS related changed
        return

    # handle each domain separately and push all touched records to PowerDNS
    for zone, records in group_by_zone(records).items():
        # todo we have to loop over all names not just zones..
        # todo proper diffing and deleting old ones
        actual = dns_client.get_rrsets(zone, records[0].name)

        # convert our database records to PowerDNS RRSet objects and push via HTTP
        expected = db_records_to_pdns_rrsets(records)

        dns_client.create_or_update_rrsets(zone, expected)


def group_by_zone(records: list) -> dict[str, list]:
    records_by_zone = {}
    for record in records:
        if record.domain not in records_by_zone:
            records_by_zone[record.domain] = []
        records_by_zone[record.domain].append(record)

    return records_by_zone


def db_records_to_pdns_rrsets(records: list):
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
        if record.type == 'PTR':
            record.content = ensure_trailing_dot(record.content)
        elif record.type == 'TXT':
            # TXT records need to be quoted in powerdns
            record.content = quote_string(record.content)

        record_content = RecordContent(record.content)
        content_group_by_type[record.name][record.type].append(record_content)

    rrsets = []
    for name, types in content_group_by_type.items():
        for type, contents in types.items():
            rrset = RRSet()
            rrset.type = type
            rrset.name = ensure_trailing_dot(name)
            rrset.ttl = get_ttl()
            rrset.records = contents
            rrsets.append(rrset)

    return rrsets
