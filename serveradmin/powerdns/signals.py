import logging

from django.conf import settings
from django.dispatch import receiver

from serveradmin.common.utils import profile
from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain
from serveradmin.serverdb.query_committer import post_commit

logger = logging.getLogger(__package__)


@receiver(post_commit)
@profile
def create_domains(sender, **kwargs):
    """Create PowerDNS domain for newly created objects

    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['created']:
        return

    domain_settings = settings.PDNS.get('domain')
    for new_object in kwargs['created']:
        servertype = new_object['servertype']

        for domain_setting in domain_settings:
            if servertype != domain_setting['servertype']:
                continue

            # The Serveradmin attribute object_id is not present in the
            # post_commit created data so we query the data again.
            attrs = domain_setting['attributes']
            queried_object = Query(
                {'hostname': new_object[attrs['name']]},
                list(attrs.values())).get()

            # All attributes are mandatory
            domain = Domain()
            domain.id = queried_object['object_id']
            domain.name = queried_object[attrs['name']]
            domain.type = queried_object[attrs['type']]
            domain.save()


@receiver(post_commit)
@profile
def delete_domains(sender, **kwargs):
    """Delete PowerDNS domain for deleted objects

    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['deleted']:
        return

    # deleted contains a list of object_ids that were deleted and no further
    # information about e.g. servertype so we just try to delete everything
    # that matches.
    #
    # @TODO: Find a way to avoid querying the database for irrelevant objects
    Domain.objects.filter(id__in=kwargs['deleted']).delete()
