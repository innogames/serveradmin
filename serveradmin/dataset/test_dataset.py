from ipaddress import ip_interface

from django.test import TestCase

from adminapi.filters import (
    Any,
    Comparison,
    Not,
    Or,
    Regexp,
    Startswith,
)
from serveradmin.dataset import Query, create


class TestQuery(TestCase):
    fixtures = ['test_dataset.json']

    def test_query_hostname(self):
        s = Query({'hostname': 'test0'}).get()
        self.assertEqual(s['hostname'], 'test0')

    def test_query_os(self):
        s = Query({'os': 'wheezy'}).get()
        self.assertEquals(s['hostname'], 'test0')

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
        self.assertEquals(s['hostname'], 'test0')

    def test_filter_comparison(self):
        hostnames = set()
        for s in Query({'game_world': Comparison('<', 2)}):
            hostnames.add(s['hostname'])

        self.assertNotIn('test0', hostnames)
        self.assertIn('test1', hostnames)
        self.assertNotIn('test2', hostnames)
        self.assertNotIn('test3', hostnames)

    def test_filter_any(self):
        hostnames = set()
        for s in Query({'hostname': Any('test1', 'test3')}):
            hostnames.add(s['hostname'])

        self.assertNotIn('test0', hostnames)
        self.assertIn('test1', hostnames)
        self.assertNotIn('test2', hostnames)
        self.assertIn('test3', hostnames)

    def test_and(self):
        pass

    def test_or(self):
        q = Query({'game_world': Or(Comparison('<', 2), Comparison('>', 7))})
        hostnames = set()
        for s in q:
            hostnames.add(s['hostname'])

        self.assertNotIn('test0', hostnames)
        self.assertIn('test1', hostnames)
        self.assertNotIn('test2', hostnames)
        self.assertIn('test3', hostnames)

    def test_not(self):
        s = Query({'os': Not('squeeze')}).get()
        self.assertEquals(s['hostname'], 'test0')

    def test_not_filter(self):
        s = Query({'os': Not(Any('squeeze', 'lenny'))}).get()
        self.assertEquals(s['hostname'], 'test0')

    def test_startswith(self):
        s = Query({'os': Startswith('whee')}).get()
        self.assertEquals(s['hostname'], 'test0')

    def test_startswith_servertype(self):
        q = Query({'servertype': Startswith('tes')})
        self.assertEquals(len(q), 4)


class TestCommit(TestCase):
    fixtures = ['test_dataset.json']

    def test_commit_query(self):
        q = Query({'hostname': 'test1'})
        s = q.get()
        s['os'] = 'wheezy'
        s['intern_ip'] = '10.16.2.1'
        q.commit()

        s = Query({'hostname': 'test1'}).get()
        self.assertEquals(s['os'], 'wheezy')
        self.assertEquals(s['intern_ip'], ip_interface('10.16.2.1'))

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


class TestCreate(TestCase):
    def test_create(self):
        s = {
            'hostname': 'test4',
            'intern_ip': '127.0.0.1',
            'servertype': 'test0',
            'os': 'squeeze',
            'database': ['pgsql']
        }
        s_res = create(s, fill_defaults=True, fill_defaults_all=True)
        self.assertEqual(s_res['hostname'], 'test4')
