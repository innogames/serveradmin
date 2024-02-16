"""Serveradmin - ip_addr_type validation tests

Copyright (c) 2021 InnoGames GmbH
"""

import logging
from ipaddress import IPv4Network

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from faker import Faker
from faker.providers import internet

from serveradmin.dataset import Query, DatasetObject
from serveradmin.serverdb.forms import ServertypeAttributeAdminForm
from serveradmin.serverdb.models import ServertypeAttribute

# TODO: Remove "InternIp" classes when intern_ip is gone.
#
# Once we eliminated the special attribute intern_ip we can get rid of the
# test classes with "InternIp" in name.


class TestIpAddrType(TransactionTestCase):
    fixtures = ['auth_user.json', 'ip_addr_type.json']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger('faker').setLevel(logging.ERROR)

    def setUp(self):
        super().setUp()
        self.faker = Faker()
        self.faker.add_provider(internet)

    def _get_server(self, servertype: str) -> DatasetObject:
        server = Query().new_object(servertype)
        server['hostname'] = self.faker.hostname()

        return server


class TestIpAddrTypeNullForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type null and intern_ip"""

    def test_server_without_intern_ip(self):
        server = self._get_server('null')
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_intern_ip(self):
        server = self._get_server('null')
        server['intern_ip'] = '10.0.0.1'

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())


class TestIpAddrTypeNullForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type null and inet attributes"""

    def test_add_inet_attribute_in_admin_panel(self):
        attr = ServertypeAttribute(
            attribute_id='ip_config', servertype_id='null')
        form = ServertypeAttributeAdminForm(
            data={
                'attribute': 'ip_config',
                'servertype': 'null',
            }, instance=attr)
        form.is_valid()
        with self.assertRaises(ValidationError):
            form.clean()


class TestIpAddrTypeHostForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type host and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server('host')
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_invalid_value(self):
        server = self._get_server('host')
        server['intern_ip'] = 'nonsense'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_network(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.0/16'

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server('host')
        first['intern_ip'] = '10.0.0.1/32'
        first.commit(user=User.objects.first())

        second = self._get_server('host')
        second['intern_ip'] = '10.0.0.1'

        with self.assertRaises(ValidationError):
            second.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_ip(self):
        first = self._get_server('host')
        first['intern_ip'] = '10.0.0.1/32'
        first['ip_config'] = '10.0.0.2/32'
        first.commit(user=User.objects.first())

        # Test "cross" duplicate attribute denial
        duplicate = self._get_server('host')
        duplicate['intern_ip'] = '10.0.0.2/32'
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_change_server_hostname(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))


class TestIpAddrTypeHostForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type host and inet attributes"""

    def test_server_without_value(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_value(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_invalid_value(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = 'nonsense'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_network(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.0/16'

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_attribute(self):
        first = self._get_server('host')
        first['intern_ip'] = '10.0.0.1/32'
        first['ip_config'] = '10.0.0.2/32'
        first.commit(user=User.objects.first())

        second = self._get_server('host')
        second['intern_ip'] = '10.0.0.3/32'
        second['ip_config'] = '10.0.0.2/32'

        with self.assertRaises(ValidationError):
            second.commit(user=User.objects.first())

    def test_server_overlaps_with_network(self):
        network = self._get_server('network')
        network['intern_ip'] = '10.0.0.5/32'
        network['ip_config'] = '10.0.1.5/32'
        network.commit(user=User.objects.first())

        # An ip_address must not collide with the smallest possible network
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.1.5/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server('host')
        first['intern_ip'] = '10.0.0.1/32'
        first['ip_config'] = '10.0.0.2/32'
        first.commit(user=User.objects.first())

        # Test "cross" duplicate attribute denial
        duplicate = self._get_server('host')
        duplicate['intern_ip'] = '10.0.0.3/32'
        duplicate['ip_config'] = '10.0.0.1/32'
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_different_attrs(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        server.commit(user=User.objects.first())

        other_attribute = self._get_server('host')
        other_attribute['intern_ip'] = '10.0.0.3/32'
        other_attribute['ip_config_new'] = '10.0.0.2/32'
        self.assertIsNone(other_attribute.commit(user=User.objects.first()))

    def test_server_with_duplicate_inet_for_loadbalancer(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server.commit(user=User.objects.first())

        duplicate = self._get_server('host')
        duplicate['intern_ip'] = '10.0.0.2/32'
        duplicate['ip_config'] = '10.0.0.1/32'
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_change_server_hostname(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))


class TestIpAddrTypeLoadbalancerForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type loadbalancer and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server('loadbalancer')
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_ip_network(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.0/16'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server('loadbalancer')
        first['intern_ip'] = '10.0.0.1/32'
        first.commit(user=User.objects.first())

        second = self._get_server('loadbalancer')
        second['intern_ip'] = '10.0.0.1/32'
        self.assertIsNone(second.commit(user=User.objects.first()))

    def test_change_server_hostname(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))


class TestIpAddrTypeLoadbalancerForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type loadbalancer and inet attrs"""

    def test_server_without_value(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_value(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_ip_network(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.0/16'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_attribute(self):
        first = self._get_server('loadbalancer')
        first['intern_ip'] = '10.0.0.1/32'
        first['ip_config'] = '10.0.0.2/32'
        first.commit(user=User.objects.first())

        second = self._get_server('loadbalancer')
        second['intern_ip'] = '10.0.0.1/32'
        second['ip_config'] = '10.0.0.2/32'
        self.assertIsNone(second.commit(user=User.objects.first()))

    def test_server_with_duplicate_inet_ip(self):
        first = self._get_server('loadbalancer')
        first['intern_ip'] = '10.0.0.1/32'
        first['ip_config'] = '10.0.0.2/32'
        first.commit(user=User.objects.first())

        # Test "cross" duplicate attribute is denied
        duplicate = self._get_server('host')
        duplicate['intern_ip'] = '10.0.0.2/32'
        duplicate['ip_config'] = '10.0.0.1/32'
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_different_attrs(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        server.commit(user=User.objects.first())

        duplicate = self._get_server('loadbalancer')
        duplicate['intern_ip'] = '10.0.0.3/32'
        duplicate['ip_config_new'] = '10.0.0.2/32'
        self.assertIsNone(duplicate.commit(user=User.objects.first()))

    def test_change_server_hostname(self):
        server = self._get_server('loadbalancer')
        server['intern_ip'] = '10.0.0.1/32'
        server['ip_config'] = '10.0.0.2/32'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))


class TestIpAddrTypeNetworkForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type network and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server('network')
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/16'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_invalid_value(self):
        server = self._get_server('host')
        server['intern_ip'] = 'nonsense'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_invalid_network(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.5/16'  # Invalid: Has host bits set

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_address(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.1/32'  # Just a very small network
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_network_overlaps(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first.commit(user=User.objects.first())

        overlaps = self._get_server('network')
        overlaps['intern_ip'] = '10.0.0.0/28'
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_change_server_network_overlaps(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        host = Query({'hostname': first['hostname']}, ['intern_ip'])
        host.update(intern_ip=IPv4Network('10.0.0.0/28'))
        self.assertIsNone(host.commit(user=User.objects.first()))

    def test_server_network_overlaps_inet(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        overlaps = self._get_server('network')
        overlaps['intern_ip'] = '10.0.1.0/28'
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_server_network_overlaps_other_servertype(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first.commit(user=User.objects.first())

        # A network can overlap with networks of other servertypes
        overlaps = self._get_server('other_network')
        overlaps['intern_ip'] = '10.0.0.0/28'
        self.assertIsNone(overlaps.commit(user=User.objects.first()))

    def test_change_server_hostname(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/30'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))


class TestIpAddrTypeNetworkForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type network and inet attrs"""

    def test_server_without_value(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/16'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_value(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/30'
        server['ip_config'] = '10.0.1.0/30'
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_with_invalid_value(self):
        server = self._get_server('host')
        server['intern_ip'] = '10.0.0.0/30'
        server['ip_config'] = 'nonsense'
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_invalid_network(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/16'
        server['ip_config'] = '10.0.1.5/28'  # Invalid: Has host bits set

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_address(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.1/32'  # Just a very small network
        server['ip_config'] = '10.0.1.0/32'  # Just a very small network
        self.assertIsNone(server.commit(user=User.objects.first()))

    def test_server_network_overlaps(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        overlaps = self._get_server('network')
        overlaps['intern_ip'] = '10.0.3.0/30'
        overlaps['ip_config'] = '10.0.1.0/28'
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_change_server_network_overlaps(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        host = Query({'hostname': first['hostname']}, ['ip_config'])
        host.update(ip_config=IPv4Network('10.0.1.0/28'))
        self.assertIsNone(host.commit(user=User.objects.first()))

    def test_server_network_overlaps_intern_ip(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first.commit(user=User.objects.first())

        overlaps = self._get_server('network')
        overlaps['intern_ip'] = '10.0.1.0/28'
        overlaps['ip_config'] = '10.0.0.0/28'
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_server_network_is_equal(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        equal = self._get_server('network')
        equal['intern_ip'] = '10.0.2.0/30'
        equal['ip_config'] = '10.0.1.0/30'
        with self.assertRaises(ValidationError):
            equal.commit(user=User.objects.first())

    def test_server_network_overlaps_other_servertype(self):
        first = self._get_server('network')
        first['intern_ip'] = '10.0.0.0/30'
        first['ip_config'] = '10.0.1.0/30'
        first.commit(user=User.objects.first())

        # A network can overlap with networks of other servertypes
        overlaps = self._get_server('other_network')
        overlaps['intern_ip'] = '10.0.0.0/28'
        overlaps['ip_config'] = '10.0.1.0/30'
        self.assertIsNone(overlaps.commit(user=User.objects.first()))

    def test_server_with_duplicate_inet_different_attrs(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/30'
        server['ip_config'] = '10.0.1.0/30'
        server.commit(user=User.objects.first())

        duplicate = self._get_server('network')
        duplicate['intern_ip'] = '10.0.2.0/30'
        duplicate['ip_config_new'] = '10.0.1.0/30'
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_change_server_hostname(self):
        server = self._get_server('network')
        server['intern_ip'] = '10.0.0.0/30'
        server['ip_config'] = '10.0.1.0/30'
        server.commit(user=User.objects.first())

        to_rename = Query({'hostname': server['hostname']}, ['hostname'])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsNone(to_rename.commit(user=User.objects.first()))
