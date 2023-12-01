import logging
import time

from serveradmin.powerdns.sync import sync_records
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

    # Is any of the updated objects mapped to a PowerDNS domain?
    from serveradmin.powerdns.models import Record
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    records = Record.objects.filter(object_id__in=object_ids).all()
    logger.error(f"matze records {records}")
    if not records:
        # nothing DNS related changed
        return

    start = time.time()
    sync_records(records)
    logger.info(f"Matze Sync took {time.time() - start}s")
