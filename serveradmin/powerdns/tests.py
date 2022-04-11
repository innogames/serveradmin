from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain, Record
from serveradmin.powerdns.signals import (
    create_domains,
    delete_domains,
    update_domains,
)


def _create_serveradmin_domain():
    serveradmin_domain = Query().new_object('domain')
    serveradmin_domain['hostname'] = 'innogames.net'
    serveradmin_domain['type'] = 'NATIVE'
    serveradmin_domain.commit(user=User.objects.first())

    return serveradmin_domain


def _create_powerdns_domain():
    domain = Domain()
    domain.id = 1
    domain.name = 'innogames.net'
    domain.type = 'NATIVE'
    domain.save()

    return domain


class DomainTests(TransactionTestCase):
    reset_sequences = True
    databases = '__all__'
    fixtures = ['powerdns_auth.json', 'powerdns_serverdb.json']

    def tearDown(self) -> None:
        # Because PowerDNS models are unmanaged we need to take care of
        # cleaning up after each test case on our own.
        Domain.objects.all().delete()
        Record.objects.all().delete()

    def test_create_powerdns_domain_from_post_commit_signal(self):
        serveradmin_domain = _create_serveradmin_domain()

        sender = None
        created = [serveradmin_domain]
        create_domains(sender, created=created)

        self.assertEqual(Domain.objects.count(), 1)

    def test_delete_powerdns_domain_from_post_commit_signal(self):
        domain = _create_powerdns_domain()

        self.assertEqual(Domain.objects.count(), 1)

        sender = None
        deleted = [domain.id]
        delete_domains(sender, deleted=deleted)

        self.assertEqual(Domain.objects.count(), 0)

    def test_update_powerdns_domain_name_from_post_commit_signal(self):
        # update_domains requires a Serveradmin object to be present
        _create_serveradmin_domain()
        _create_powerdns_domain()

        self.assertEqual(
            Domain.objects.filter(name='innogames.net').count(), 1)

        sender = None
        changed = [{
            'object_id': 1,
            'hostname': {'action': 'update', 'new': 'innogames.de'},
        }]
        update_domains(sender, changed=changed)

        self.assertEqual(
            Domain.objects.filter(name='innogames.de').count(), 1)

    def test_update_powerdns_domain_type_from_post_commit_signal(self):
        # update_domains requires a Serveradmin object to be present
        _create_serveradmin_domain()
        _create_powerdns_domain()

        self.assertEqual(
            Domain.objects.filter(type='NATIVE').count(), 1)

        sender = None
        changed = [{
            'object_id': 1,
            'type': {'action': 'update', 'new': 'MASTER'},
        }]
        update_domains(sender, changed=changed)

        self.assertEqual(
            Domain.objects.filter(type='MASTER').count(), 1)
