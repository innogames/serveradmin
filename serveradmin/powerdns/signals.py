import logging
import time

from django.db.models import Q

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
    records = Record.objects.filter(object_ids__contains=object_ids).all()
    sync_records(records)


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
    records = Record.objects.filter(object_ids__cntains=object_ids).all()
    sync_records(records)


@profile
def update_records(sender, **kwargs):
    """Update PowerDNS domain when changed
    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['changed']:
        return

    # todo: support changes like this, the following code is not fully working...and not even clean code
    # [{'domain': {'action': 'multi', 'add': ['xx3.example.com'], 'remove': ['xx4.example.com']}, 'object_id': 11384}]
    # we have to update xx3.example.com + xx4.example.com and not just the new one
    from serveradmin.powerdns.models import Record

    # Is any of the updated objects mapped to a PowerDNS domain?
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    records = Record.objects.filter(object_ids__contains=object_ids).all()

    sync_records(records)
    logger.info(f"object to delete {kwargs['changed']} {object_ids}")
