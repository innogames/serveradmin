from random import random
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from serveradmin.dataset import Query
from serveradmin.powerdns.models import Domain, Record

domain_config = settings.POWERDNS['domain']


def create_test_object(servertype: str, **kwargs: Any) -> Query:
    obj = Query().new_object(servertype)
    obj['hostname'] = str(random())

    for key, value in kwargs.items():
        obj[key] = value

    obj.commit(user=User.objects.first())

    return Query({'hostname': obj['hostname']}, list(obj.keys()))


class PowerDNSTests(TransactionTestCase):
    databases = ['default', 'powerdns']
    fixtures = ['auth.json', 'serverdb.json']

    def setUp(self) -> None:
        super().setUp()

        self.user = User.objects.first()
        self.soa = 'localhost admin@example.com 1 900 3600 900 300'
        self.ns = {'pdns1.example.com', 'pdns2.example.com'}
        self.ttl = 3600
        self.a = '10.0.0.1'
        self.aaaa = '2a00:1f78:fffd:4013::0001'
        self.txt = {'txt_example_1=abc', 'txt_example_2=def'}
        self.sshfp = {
            'host.example.com.  SSHFP 2 1 123456789abcdef67890123456789abcdef67890',
            'host.example.com.  SSHFP 4 2 0123456789abcdef67890123456789abcdef6789',
        }

    def tearDown(self) -> None:
        super().tearDown()

        # When running tests data inserted to the powerdns is not cleaned up.
        Record.objects.all().delete()
        Domain.objects.all().delete()
