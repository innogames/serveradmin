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
    sync_records(records, False)


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

    # todo delete them, in best case AFTER the commit went through
    records_to_delete = Record.objects.filter(object_ids__contains=object_ids).all()
    #sync_records(records)


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
    # [{'intern_ip': {'action': 'update', 'new': '212.53.194.143', 'old': '212.53.194.144'}, 'object_id': 549446}]
    # we have to update xx3.example.com + xx4.example.com and not just the new one
    from serveradmin.powerdns.models import Record, RecordSetting

    # changes on the main object
    #object_ids = [changed['object_id'] for changed in kwargs['changed']]
    object_ids = []

    # first get all attribute fields which could potentially be related to a DNS record...

    #domain_attributes = get_domain_attributes()
    #logger.warning(f"domain_attributes {domain_attributes}")
    all_relevant_attributes = get_all_attributes()
    logger.warning(f"all_attributes {all_relevant_attributes}")

    # then check in the changes and extract all such domain from the before+after changes.
    touched_domains = set()
    for changes in kwargs['changed']:
        logger.warning(f"changes {changes}")

        # change = {'intern_ip': {'action': 'update', 'new': '212.53.194.143', 'old': '212.53.194.144'}, 'object_id': 549446}
        for field, change in changes.items():
            if field == 'object_id':
                continue
            if field in all_relevant_attributes:
                print(f"field {field} in all_attributes!! {change}")
                object_ids.append(changes['object_id'])
                break

#        logger.warning(f"touched domains {touched_domains}")
#        logger.warning(f"changes  {changes}")
#
#        for domain_attribute in domain_attributes:
#            domain_attribute = str(domain_attribute)
#            if domain_attribute in changes:
#                touched_domains.update(changes[domain_attribute].get('add', None))
#                touched_domains.update(changes[domain_attribute].get('remove', None))

    if not object_ids:
        return

    touched_domains = list(filter(None, touched_domains))
    logger.warning(f"touched domains {touched_domains}")

    records = Record.objects.filter(Q(object_ids__contains=object_ids)|Q(domain__in=touched_domains)).all()
    logger.info(records)
    sync_records(records, False)

    logger.info(f"object to update {kwargs['changed']} {object_ids}")


def get_domain_attributes():
    """Get all attributes which could be related to a DNS record
    :return:
    """
    from serveradmin.powerdns.models import RecordSetting

    domain_attributes = (RecordSetting.objects.exclude(domain__isnull=True)
                         .distinct('domain').values_list('domain', flat=True))

    return set(domain_attributes)


def get_all_attributes():
    """Get all attributes which could be related to a DNS record
    :return:
    """
    from serveradmin.powerdns.models import RecordSetting

    # todo: this could be cached...even if the querries are very fast
    columns = 'source_value', 'source_value_special', 'domain'

    distinct_values = ['hostname']
    for column in columns:
        distinct_values += list(RecordSetting.objects.values_list(column, flat=True).distinct())

    return set(filter(None, distinct_values))
