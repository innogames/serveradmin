"""Serveradmin

Copyright (c) 2018 InnoGames GmbH
"""

from ipaddress import IPv4Address
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from adminapi.filters import (
    Any,
    Not,
    Regexp,
    StartsWith,
)
from serveradmin.dataset import Query


class TestQuery(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def test_query_hostname(self):
        s = Query({'hostname': 'test0'}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_query_os(self):
        s = Query({'os': 'wheezy'}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_query_iterate(self):
        hostnames = set()
        for server in Query({}):
            hostnames.add(server['hostname'])

        self.assertIn('test0', hostnames)
        self.assertIn('test1', hostnames)
        self.assertIn('test2', hostnames)
        self.assertIn('test3', hostnames)

    def test_filter_regexp(self):
        hostnames = set()
        for s in Query({'hostname': Regexp('^test[02]$')}):
            hostnames.add(s['hostname'])

        self.assertIn('test0', hostnames)
        self.assertNotIn('test1', hostnames)
        self.assertIn('test2', hostnames)

    def test_filter_regexp_servertype(self):
        s = Query({'servertype': Regexp('^test[870]')}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_filter_any(self):
        hostnames = set()
        for s in Query({'hostname': Any('test1', 'test3')}):
            hostnames.add(s['hostname'])

        self.assertNotIn('test0', hostnames)
        self.assertIn('test1', hostnames)
        self.assertNotIn('test2', hostnames)
        self.assertIn('test3', hostnames)

    def test_not(self):
        s = Query({'os': Not('squeeze')}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_not_filter(self):
        s = Query({'os': Not(Any('squeeze', 'lenny'))}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_startswith(self):
        s = Query({'os': StartsWith('whee')}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_startswith_servertype(self):
        q = Query({'servertype': StartsWith('tes')})
        self.assertEqual(len(q), 4)


class TestCommit(TransactionTestCase):
    fixtures = ['test_dataset.json']

    def test_commit_query(self):
        q = Query({'hostname': 'test1'}, ['os', 'intern_ip'])
        s = q.get()
        s['os'] = 'wheezy'
        s['intern_ip'] = IPv4Address('10.16.2.1')
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test1'}, ['os', 'intern_ip']).get()
        self.assertEqual(s['os'], 'wheezy')
        self.assertEqual(s['intern_ip'], IPv4Address('10.16.2.1'))

    def test_commit_regexp_violation(self):
        pass

    def test_commit_attr_not_exist(self):
        pass

    def test_commit_servertype(self):
        pass

    def test_commit_hostname(self):
        pass

    def test_commit_intern_ip(self):
        pass

    def test_commit_newer_data(self):
        pass
