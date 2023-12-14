import logging
import time

from serveradmin.powerdns.sync.sync import sync_records
from serveradmin.common.utils import profile

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

    object_ids = [changed['object_id'] for changed in kwargs['created']]

    from serveradmin.powerdns.models import Record
    records = Record.objects.filter(object_id__in=object_ids).all()
    sync(records)


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

    logger.info(f"object to delete {kwargs['deleted']}")

    # todo fetch deleted entries beforehand to get consistent state to sync?
    records = Record.objects.filter(object_id__in=object_ids).all()
    sync(records)


@profile
def update_records(sender, **kwargs):
    """Update PowerDNS domain when changed
    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['changed']:
        return

    # Is any of the updated objects mapped to a PowerDNS domain?
    from serveradmin.powerdns.models import Record
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    records = Record.objects.filter(object_id__in=object_ids).all()

    sync(records)


def sync(records):
    if not records:
        return

    start = time.time()
    sync_records(records)
    logger.info(f"DNS sync of {len(records)} took {time.time() - start}s {records}")
