from time import time

from django.conf import settings
from django.db import transaction
from django.dispatch import receiver

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain, Record
from serveradmin.serverdb.query_committer import post_commit

config = settings.POWERDNS['domain']
TYPE = config['type']
SOA = config['soa']
NS = config['ns']
ATTRS = ['hostname', TYPE, SOA, NS]


@receiver(post_commit)
def synchronize_powerdns_domains(sender, **kwargs) -> None:
    """Synchronize PowerDNS domains

    Apply all changes to objects of servertype domain to the PowerDNS domains.

    :param sender:
    :param kwargs:
    :return:
    """

    if kwargs['created']:
        for created in kwargs['created']:
            if created['servertype'] in config['servertypes']:
                _create_domain(created['hostname'])
    if kwargs['changed']:
        for changed in kwargs['changed']:
            if _must_change(changed):
                _update_domain(changed)
    if kwargs['deleted']:
        # Deletes all records automatically due to DELETE CASCADE
        Domain.objects.filter(id__in=kwargs['deleted']).delete()


def _create_domain(hostname: str) -> None:
    """Create PowerDNS domain

    Create PowerDNS domain and required DNS records such as NS and SOA.

    :param hostname:
    :return:
    """

    # There is no object_id in post_commit signal data for created objects
    s_object = Query({'hostname': hostname}, ATTRS).get()

    with transaction.atomic():
        domain = Domain.objects.create(
            id=s_object['object_id'],
            name=s_object['hostname'],
            type=s_object[TYPE])

        Record.objects.create(
            domain=domain,
            name=s_object['hostname'],
            type='SOA',
            content=s_object[SOA],
            object_id=s_object['object_id'])

        for nameserver in s_object[NS]:
            Record.objects.create(
                domain=domain,
                name=s_object['hostname'],
                type='NS',
                content=nameserver,
                object_id=s_object['object_id'])


def _must_change(change: dict) -> bool:
    """Has changes for PowerDNS domains ?

    :param change:
    :return:
    """

    # Avoid querying the database if nothing relevant has changed
    if not any([attribute in ATTRS for attribute in change]):
        return False

    return Domain.objects.filter(id=change['object_id']).exists()


def _update_domain(change: dict) -> None:
    """Update PowerDNS domain

    Apply changes to PowerDNS domains and its DNS records such as SOA and TXT.

    :param change:
    :return:
    """

    with transaction.atomic():
        domain = Domain.objects.get(id=change['object_id'])

        if 'hostname' in change:
            new_hostname = change['hostname']['new']
            domain.name = new_hostname
            domain.save()
            Record.objects.filter(
                domain_id=domain.id, type__in=('NS', 'SOA')
            ).update(name=new_hostname, change_date=int(time()))

        if NS in change:
            Record.objects.filter(
                domain_id=domain.id, type='NS',
                content__in=change[NS]['remove']).delete()

            for nameserver in change[NS]['add']:
                Record.objects.create(
                    domain=domain, name=domain.name, type='NS',
                    content=nameserver)

        if SOA in change:
            Record.objects.filter(
                domain_id=domain.id, type='SOA', content=change[SOA]['old']
            ).update(
                content=change[SOA]['new'], change_date=int(time()))

        if TYPE in change:
            domain.type = change[TYPE]['new']
            domain.save()
