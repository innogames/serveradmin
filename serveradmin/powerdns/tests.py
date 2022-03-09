from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain
from serveradmin.powerdns.signals import create_domains, delete_domains


class DomainTests(TransactionTestCase):
    databases = '__all__'
    fixtures = ['powerdns_auth.json', 'powerdns_serverdb.json']

    def test_create_powerdns_domain_from_post_commit_signal(self):
        serveradmin_domain = Query().new_object('domain')
        serveradmin_domain['hostname'] = 'innogames.net'
        serveradmin_domain['type'] = 'NATIVE'
        serveradmin_domain.commit(user=User.objects.first())

        sender = None
        created = [serveradmin_domain]
        create_domains(sender, created=created)

        self.assertEqual(Domain.objects.count(), 1)

    def test_delete_powerdns_domain_from_post_commit_signal(self):
        domain = Domain()
        domain.id = 1
        domain.name = 'innogames.net'
        domain.type = 'NATIVE'
        domain.save()

        self.assertEqual(Domain.objects.count(), 1)

        sender = None
        deleted = [domain.id]
        delete_domains(sender, deleted=deleted)

        self.assertEqual(Domain.objects.count(), 0)
