from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain


class _DomainTestCase(TransactionTestCase):
    databases = {'default', 'pdns'}
    fixtures = ['powerdns_auth.json', 'powerdns_serverdb.json']


class TestCreateDomain(_DomainTestCase):
    def test_create_domain(self):
        serveradmin_domain = Query().new_object('domain')
        serveradmin_domain['hostname'] = 'innogames.net'
        serveradmin_domain['type'] = 'NATIVE'
        serveradmin_domain.commit(user=User.objects.first())

        # object_id is not present on freshly created objects
        object_id = Query({'hostname': 'innogames.net'}).get()['object_id']

        query_set_filter = {
            'name': 'innogames.net',
            'type': 'NATIVE',
            'id': object_id,
        }

        self.assertTrue(
            Domain.objects.filter(**query_set_filter).exists(),
            'PowerDNS domain not found')


class TestDeleteDomain(_DomainTestCase):
    def test_delete_domain(self):
        serveradmin_domain = Query().new_object('domain')
        serveradmin_domain['hostname'] = 'innogames.net'
        serveradmin_domain['type'] = 'NATIVE'
        serveradmin_domain.commit(user=User.objects.first())

        # object_id is not present on freshly created objects
        qs = Query({'hostname': 'innogames.net'})
        object_id = qs.get()['object_id']
        qs.delete()
        qs.commit(user=User.objects.first())

        self.assertEqual(
            Domain.objects.filter(id=object_id).count(), 0,
            f'No PowerDNS domain with id {object_id} should exist')
