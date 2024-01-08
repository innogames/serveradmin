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
    records = Record.objects.filter(object_id__in=object_ids).all()
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
    records = Record.objects.filter(object_id__in=object_ids).all()
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
    from serveradmin.powerdns.models import Record, RecordSetting

    # first get all attribute fields which could potentially be related to a DNS record...
    domain_attributes = (RecordSetting.objects.exclude(domain__isnull=True)
                         .distinct('domain').values_list('domain', flat=True))
    logger.warning(f"domain_attributes {domain_attributes}")

    # then check in the changes and extract all such domain from the before+after changes.
    touched_domains = set()
    for changes in kwargs['changed']:
        logger.warning(f"touched domains {touched_domains}")

        for domain_attribute in domain_attributes:
            domain_attribute = str(domain_attribute)
            if domain_attribute in changes:
                touched_domains.update(changes[domain_attribute]['add'])
                touched_domains.update(changes[domain_attribute]['remove'])

    logger.warning(f"touched domains {touched_domains}")

    # Is any of the updated objects mapped to a PowerDNS domain?
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    records = Record.objects.filter(Q(object_id__in=object_ids)|Q(domain__in=touched_domains)).all()

    sync_records(records)
