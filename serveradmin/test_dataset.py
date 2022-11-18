"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
from datetime import datetime, timezone, tzinfo, timedelta, date
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from netaddr import EUI

from adminapi.filters import (
    Any,
    Not,
    Regexp,
    StartsWith,
)
from serveradmin.dataset import Query


class TestQuery(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

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
        self.assertEqual(len(q), 5)


class TestCommit(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

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


class TestAttributeDatetime(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute(self):
        """Try to set and retrieve a datetime attribute"""
        dt = datetime.utcnow().replace(tzinfo=timezone.utc)
        q = Query({'hostname': 'test0'}, ['last_edited'])
        s = q.get()
        s['last_edited'] = dt
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['last_edited']).get()
        self.assertEqual(s['last_edited'], dt)

    def test_utc_conversion(self):
        """Ensure datetimes are converted to UTC

        Users can pass datetimes in any timezone they want. Serveradmin will
        transform them to UTC and only ever return them in UTC form.
        """

        class TZ(tzinfo):
            def utcoffset(self, dt):
                return timedelta(minutes=+3)

        q = Query({'hostname': 'test0'}, ['last_edited'])
        s = q.get()
        s['last_edited'] = datetime(1970, 1, 1, 0, 3, 0).replace(tzinfo=TZ())
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['last_edited']).get()
        self.assertEqual(str(s['last_edited']), '1970-01-01 00:00:00+00:00')


class TestAttributeDate(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute(self):
        """Try to set and retrieve a date attribute"""

        dt = date.today()
        q = Query({'hostname': 'test0'}, ['created'])
        s = q.get()
        s['created'] = dt
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['created']).get()
        self.assertEqual(s['created'], dt)


class TestAttributeMac(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute(self):
        """Try to set and retrieve a MAC attribute"""

        mac_address = EUI('00:11:22:33:44:55')
        q = Query({'hostname': 'test0'}, ['mac_address'])
        s = q.get()
        s['mac_address'] = mac_address
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['mac_address']).get()
        self.assertEqual(s['mac_address'], mac_address)


class TestAttributeInet(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute_ipv4_address(self):
        """Try to set and retrieve a IPv4Address from an inet attribute"""

        ipv4_address = IPv4Address('10.0.0.1')
        q = Query({'hostname': 'test0'}, ['inet_address'])
        s = q.get()
        s['inet_address'] = ipv4_address
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['inet_address']).get()
        self.assertEqual(s['inet_address'], ipv4_address)

    def test_set_attribute_ipv6_address(self):
        """Try to set and retrieve a IPv6Address from an inet attribute"""

        ipv6_address = IPv6Address('0100::')
        q = Query({'hostname': 'test0'}, ['inet_address'])
        s = q.get()
        s['inet_address'] = ipv6_address
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test0'}, ['inet_address']).get()
        self.assertEqual(s['inet_address'], ipv6_address)

    def test_set_attribute_ipv4_network(self):
        """Try to set and retrieve a IPv4Network from an inet attribute"""

        ipv4_network = IPv4Network('10.0.0.0/24')
        q = Query({'hostname': 'test4'}, ['inet_address'])
        s = q.get()
        s['inet_address'] = ipv4_network
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test4'}, ['inet_address']).get()
        self.assertEqual(s['inet_address'], ipv4_network)

    def test_set_attribute_ipv6_network(self):
        """Try to set and retrieve a IPv6Network from an inet attribute"""

        ipv6_network = IPv6Network('0100::/64')
        q = Query({'hostname': 'test4'}, ['inet_address'])
        s = q.get()
        s['inet_address'] = ipv6_network
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test4'}, ['inet_address']).get()
        self.assertEqual(s['inet_address'], ipv6_network)


class TestAttributeNumber(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute(self):
        """Try set and retrieve a number attribute"""

        game_world = 42
        q = Query({'hostname': 'test2'}, ['game_world'])
        s = q.get()
        s['game_world'] = game_world
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test2'}, ['game_world']).get()
        self.assertEqual(s['game_world'], game_world)


class TestAttributeBoolean(TransactionTestCase):
    fixtures = ['test_dataset.json', 'auth_user.json']

    def test_set_attribute(self):
        """Try to set and retrieve a boolean attribute"""

        has_monitoring = True
        q = Query({'hostname': 'test2'}, ['has_monitoring'])
        s = q.get()
        s['has_monitoring'] = has_monitoring
        q.commit(user=User.objects.first())

        s = Query({'hostname': 'test2'}, ['has_monitoring']).get()
        self.assertEqual(s['has_monitoring'], has_monitoring)
