import logging

from django.conf import settings

from serveradmin.common.utils import profile
from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain
from serveradmin.powerdns.utils import DomainSettings

logger = logging.getLogger(__package__)


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


@profile
def update_domains(sender, **kwargs):
    """Update PowerDNS domain when changed

    :param sender:
    :param kwargs:
    :return:
    """

    if not kwargs['changed']:
        return

    # Is any of the updated objects mapped to PowerDNS domain ?
    object_ids = [changed['object_id'] for changed in kwargs['changed']]
    domains_to_update = Domain.objects.filter(id__in=object_ids)
    if not domains_to_update.exists():
        return

    domain_settings = DomainSettings()
    for domain in domains_to_update:
        attributes = domain_settings.get_attributes() + ['servertype']
        # @TODO Find a way to avoid this extra Query if possible
        queried_object = Query({'object_id': domain.id}, attributes).get()
        servertype = queried_object['servertype']
        this_settings = domain_settings.get_settings(servertype)
        changed_object = next(
            filter(lambda o: o['object_id'] == domain.id, kwargs['changed']))

        has_changed = False
        for pdns_key, sa_key in this_settings['attributes'].items():
            if sa_key not in changed_object.keys():
                continue

            has_changed = True
            setattr(domain, pdns_key, changed_object[sa_key]['new'])

        if has_changed:
            domain.save()
