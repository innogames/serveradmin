"""Serveradmin - ip_addr_type validation tests

Copyright (c) 2021 InnoGames GmbH
"""

import logging
from ipaddress import IPv4Network

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TransactionTestCase
from faker import Faker
from faker.providers import internet

from adminapi import filters
from adminapi.exceptions import DatasetError
from serveradmin.dataset import Query, DatasetObject
from serveradmin.serverdb.forms import ServertypeAttributeAdminForm
from serveradmin.serverdb.models import Attribute, ServertypeAttribute
from serveradmin.serverdb.sql_generator import get_server_query

# TODO: Remove "InternIp" classes when intern_ip is gone.
#
# Once we eliminated the special attribute intern_ip we can get rid of the
# test classes with "InternIp" in name.


class TestIpAddrType(TransactionTestCase):
    fixtures = ["auth_user.json", "ip_addr_type.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.getLogger("faker").setLevel(logging.ERROR)

    def setUp(self):
        super().setUp()
        self.faker = Faker()
        self.faker.add_provider(internet)

    def _get_server(self, servertype: str) -> DatasetObject:
        server = Query().new_object(servertype)
        server["hostname"] = self.faker.hostname()

        return server


class TestIpAddrTypeNullForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type null and intern_ip"""

    def test_server_without_intern_ip(self):
        server = self._get_server("null")
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_intern_ip(self):
        server = self._get_server("null")
        server["intern_ip"] = "10.0.0.1"

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())


class TestIpAddrTypeNullForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type null and inet attributes"""

    def test_add_inet_attribute_in_admin_panel(self):
        attr = ServertypeAttribute(attribute_id="ip_config_ipv4", servertype_id="null")
        form = ServertypeAttributeAdminForm(
            data={
                "attribute": "ip_config_ipv4",
                "servertype": "null",
            },
            instance=attr,
        )
        form.is_valid()
        with self.assertRaises(ValidationError):
            form.clean()


class TestIpAddrTypeHostForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type host and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server("host")
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_invalid_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "nonsense"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_network(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.0/16"

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server("host")
        first["intern_ip"] = "10.0.0.1/32"
        first.commit(user=User.objects.first())

        second = self._get_server("host")
        second["intern_ip"] = "10.0.0.1"

        with self.assertRaises(ValidationError):
            second.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_ip(self):
        first = self._get_server("host")
        first["intern_ip"] = "10.0.0.1/32"
        first["ip_config_ipv4"] = "10.0.0.2/32"
        first.commit(user=User.objects.first())

        # Test "cross" duplicate attribute denial
        duplicate = self._get_server("host")
        duplicate["intern_ip"] = "10.0.0.2/32"
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_change_server_hostname(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeHostForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type host and inet attributes"""

    def test_server_without_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_invalid_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "nonsense"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_network(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.0/16"

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_attribute(self):
        first = self._get_server("host")
        first["intern_ip"] = "10.0.0.1/32"
        first["ip_config_ipv4"] = "10.0.0.2/32"
        first.commit(user=User.objects.first())

        second = self._get_server("host")
        second["intern_ip"] = "10.0.0.3/32"
        second["ip_config_ipv4"] = "10.0.0.2/32"

        with self.assertRaises(ValidationError):
            second.commit(user=User.objects.first())

    def test_server_overlaps_with_network(self):
        network = self._get_server("route_network")
        network["intern_ip"] = "10.0.0.5/32"
        network["ip_config_ipv4"] = "10.0.1.5/32"
        network.commit(user=User.objects.first())

        # An ip_address must not collide with the smallest possible network
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.1.5/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server("host")
        first["intern_ip"] = "10.0.0.1/32"
        first["ip_config_ipv4"] = "10.0.0.2/32"
        first.commit(user=User.objects.first())

        # Test "cross" duplicate attribute denial
        duplicate = self._get_server("host")
        duplicate["intern_ip"] = "10.0.0.3/32"
        duplicate["ip_config_ipv4"] = "10.0.0.1/32"
        with self.assertRaises(ValidationError):
            duplicate.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_different_attrs(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        server.commit(user=User.objects.first())

        other_attribute = self._get_server("host")
        other_attribute["intern_ip"] = "10.0.0.3/32"
        other_attribute["ip_config_new"] = "10.0.0.2/32"
        self.assertIsInstance(other_attribute.commit(user=User.objects.first()), int)

    def test_server_with_duplicate_inet_ip(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        server.commit(user=User.objects.first())

        # Duplicate attribute is allowed because of different inet attribute type
        duplicate = self._get_server("loadbalancer")
        duplicate["intern_ip"] = "10.0.0.2/32"
        duplicate["ip_config_ipv4"] = "10.0.0.1/32"
        self.assertIsInstance(duplicate.commit(user=User.objects.first()), int)

    def test_change_server_hostname(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeLoadbalancerForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type loadbalancer and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server("loadbalancer")
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_ip_network(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.0/16"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_intern_ip(self):
        first = self._get_server("loadbalancer")
        first["intern_ip"] = "10.0.0.1/32"
        first.commit(user=User.objects.first())

        second = self._get_server("loadbalancer")
        second["intern_ip"] = "10.0.0.1/32"
        self.assertIsInstance(second.commit(user=User.objects.first()), int)

    def test_change_server_hostname(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeLoadbalancerForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type loadbalancer and inet attrs"""

    def test_server_without_value(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_value(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_ip_network(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.0/16"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_duplicate_inet_attribute(self):
        first = self._get_server("loadbalancer")
        first["intern_ip"] = "10.0.0.1/32"
        first["ip_config_ipv4"] = "10.0.0.2/32"
        first.commit(user=User.objects.first())

        second = self._get_server("loadbalancer")
        second["intern_ip"] = "10.0.0.1/32"
        second["ip_config_ipv4"] = "10.0.0.2/32"
        self.assertIsInstance(second.commit(user=User.objects.first()), int)

    def test_server_with_duplicate_inet_ip(self):
        first = self._get_server("loadbalancer")
        first["intern_ip"] = "10.0.0.1/32"
        first["ip_config_ipv4"] = "10.0.0.2/32"
        first.commit(user=User.objects.first())

        # Duplicate attribute is allowed because of different inet attribute type
        duplicate = self._get_server("host")
        duplicate["intern_ip"] = "10.0.0.2/32"
        duplicate["ip_config_ipv4"] = "10.0.0.1/32"
        self.assertIsInstance(duplicate.commit(user=User.objects.first()), int)

    def test_server_with_duplicate_inet_different_attrs(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        server.commit(user=User.objects.first())

        duplicate = self._get_server("loadbalancer")
        duplicate["intern_ip"] = "10.0.0.3/32"
        duplicate["ip_config_new"] = "10.0.0.2/32"
        self.assertIsInstance(duplicate.commit(user=User.objects.first()), int)

    def test_change_server_hostname(self):
        server = self._get_server("loadbalancer")
        server["intern_ip"] = "10.0.0.1/32"
        server["ip_config_ipv4"] = "10.0.0.2/32"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeNetworkForInternIp(TestIpAddrType):
    """Most important tests for ip_addr_type network and intern_ip"""

    def test_server_without_value(self):
        server = self._get_server("route_network")
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_value(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/16"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_invalid_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "nonsense"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_invalid_network(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.5/16"  # Invalid: Has host bits set

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_address(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.1/32"  # Just a very small network
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_network_overlaps(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first.commit(user=User.objects.first())

        overlaps = self._get_server("route_network")
        overlaps["intern_ip"] = "10.0.0.0/28"
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_change_server_network_overlaps(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        host = Query({"hostname": first["hostname"]}, ["intern_ip"])
        host.update(intern_ip=IPv4Network("10.0.0.0/28"))
        self.assertIsInstance(host.commit(user=User.objects.first()), int)

    def test_server_network_overlaps_inet(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        overlaps = self._get_server("route_network")
        overlaps["intern_ip"] = "10.0.1.0/28"
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_server_network_overlaps_other_servertype(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first.commit(user=User.objects.first())

        # A network can overlap with networks of other servertypes
        overlaps = self._get_server("provider_network")
        overlaps["intern_ip"] = "10.0.0.0/28"
        self.assertIsInstance(overlaps.commit(user=User.objects.first()), int)

    def test_change_server_hostname(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/30"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeNetworkForInetAttributes(TestIpAddrType):
    """Most important tests for ip_addr_type network and inet attrs"""

    def test_server_without_value(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/16"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_value(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/30"
        server["ip_config_ipv4"] = "10.0.1.0/30"
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_with_invalid_value(self):
        server = self._get_server("host")
        server["intern_ip"] = "10.0.0.0/30"
        server["ip_config_ipv4"] = "nonsense"
        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_invalid_network(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/16"
        server["ip_config_ipv4"] = "10.0.1.5/28"  # Invalid: Has host bits set

        with self.assertRaises(ValidationError):
            server.commit(user=User.objects.first())

    def test_server_with_ip_address(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.1/32"  # Just a very small network
        server["ip_config_ipv4"] = "10.0.1.0/32"  # Just a very small network
        self.assertIsInstance(server.commit(user=User.objects.first()), int)

    def test_server_network_overlaps(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        overlaps = self._get_server("route_network")
        overlaps["intern_ip"] = "10.0.3.0/30"
        overlaps["ip_config_ipv4"] = "10.0.1.0/28"
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_change_server_network_overlaps(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        host = Query({"hostname": first["hostname"]}, ["ip_config_ipv4"])
        host.update(ip_config_ipv4=IPv4Network("10.0.1.0/28"))
        self.assertIsInstance(host.commit(user=User.objects.first()), int)

    def test_server_network_overlaps_intern_ip(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first.commit(user=User.objects.first())

        overlaps = self._get_server("route_network")
        overlaps["intern_ip"] = "10.0.1.0/28"
        overlaps["ip_config_ipv4"] = "10.0.0.0/28"
        with self.assertRaises(ValidationError):
            overlaps.commit(user=User.objects.first())

    def test_server_network_is_equal(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        equal = self._get_server("route_network")
        equal["intern_ip"] = "10.0.2.0/30"
        equal["ip_config_ipv4"] = "10.0.1.0/30"
        with self.assertRaises(ValidationError):
            equal.commit(user=User.objects.first())

    def test_server_network_overlaps_other_servertype(self):
        first = self._get_server("route_network")
        first["intern_ip"] = "10.0.0.0/30"
        first["ip_config_ipv4"] = "10.0.1.0/30"
        first.commit(user=User.objects.first())

        # A network can overlap with networks of other servertypes
        overlaps = self._get_server("provider_network")
        overlaps["intern_ip"] = "10.0.0.0/28"
        overlaps["ip_config_ipv4"] = "10.0.1.0/30"
        self.assertIsInstance(overlaps.commit(user=User.objects.first()), int)

    def test_change_server_hostname(self):
        server = self._get_server("route_network")
        server["intern_ip"] = "10.0.0.0/30"
        server["ip_config_ipv4"] = "10.0.1.0/30"
        server.commit(user=User.objects.first())

        to_rename = Query({"hostname": server["hostname"]}, ["hostname"])
        to_rename.update(hostname=self.faker.hostname())
        self.assertIsInstance(to_rename.commit(user=User.objects.first()), int)


class TestIpAddrTypeHostForSupernetAttr(TestIpAddrType):
    def test_af_unaware_supernet_consistent(self):
        # AF-unaware supernet attribute will be properly calculated when
        # both IPv4 and IPv6 addresses belong to the same supernet.

        network = self._get_server("route_network")
        network["intern_ip"] = "192.0.2.0/24"
        network["ip_config_ipv4"] = "192.0.2.0/24"
        network["ip_config_ipv6"] = "2001:db8::/64"
        network.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "192.0.2.1"
        server["ip_config_ipv4"] = "192.0.2.1"
        server["ip_config_ipv6"] = "2001:db8::1"
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_no_af"],
        ).get()

        self.assertEqual(server_q["supernet_no_af"], network["hostname"])

    def test_af_unaware_supernet_missing_ipv6(self):
        # AF-unaware supernet attribute will be properly calculated when
        # the IPv6 address does not belong to a supernet, even if it's present.

        network = self._get_server("route_network")
        network["intern_ip"] = "192.0.2.0/24"
        network["ip_config_ipv4"] = "192.0.2.0/24"
        network["ip_config_ipv6"] = "2001:db8::/64"
        network.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "192.0.2.1"
        server["ip_config_ipv4"] = "192.0.2.1"
        server["ip_config_ipv6"] = "2001:db8:2::1"
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_no_af"],
        ).get()

        self.assertEqual(server_q["supernet_no_af"], network["hostname"])

    def test_af_unaware_supernet_missing_ipv4(self):
        # AF-unaware supernet attribute will be properly calculated when
        # the IPv4 address does not belong to a supernet, even if it's present.

        network = self._get_server("route_network")
        network["intern_ip"] = "192.0.2.0/24"
        network["ip_config_ipv4"] = "192.0.2.0/24"
        network["ip_config_ipv6"] = "2001:db8::/64"
        network.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "198.51.100.1"
        server["ip_config_ipv4"] = "198.51.100.1"
        server["ip_config_ipv6"] = "2001:db8::1"
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_no_af"],
        ).get()

        self.assertEqual(server_q["supernet_no_af"], network["hostname"])

    def test_af_unaware_supernet_conflicting(self):
        # AF-unaware supernet attribute will fail when
        # IPv4 and IPv6 addresses belongs to different subnets.

        network1 = self._get_server("route_network")
        network1["intern_ip"] = "192.0.2.0/24"
        network1["ip_config_ipv4"] = "192.0.2.0/24"
        network1["ip_config_ipv6"] = "2001:db8:1::/64"
        network1.commit(user=User.objects.first())

        network2 = self._get_server("route_network")
        network2["intern_ip"] = "198.51.100.0/24"
        network2["ip_config_ipv4"] = "198.51.100.0/24"
        network2["ip_config_ipv6"] = "2001:db8:2::/64"
        network2.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "192.0.2.1"
        server["ip_config_ipv4"] = "192.0.2.1"
        server["ip_config_ipv6"] = "2001:db8:2::1"

        # TODO: Raise an exception once all data is cleaned up and conflicting
        # AF-unaware attributes are removed.
        # with self.assertRaises(DatasetError):
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_no_af"],
        ).get()
        self.assertIn(
            server_q["supernet_no_af"],
            [
                network1["hostname"],
                network2["hostname"],
            ],
        )

    def test_af_aware_supernet(self):
        # AF-aware supernet attributes can be calculated when
        # IPv4 and IPv6 addresses belong to different subnets.

        network_ipv4 = self._get_server("provider_network")
        network_ipv4["intern_ip"] = "192.0.2.0/24"
        network_ipv4["ip_config_ipv4"] = "192.0.2.0/24"
        network_ipv4.commit(user=User.objects.first())

        network_ipv6 = self._get_server("provider_network")
        network_ipv6["intern_ip"] = "2001:db8::/64"
        network_ipv6["ip_config_ipv6"] = "2001:db8::/64"
        network_ipv6.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "192.0.2.1"
        server["ip_config_ipv4"] = "192.0.2.1"
        server["ip_config_ipv6"] = "2001:db8::1"
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_ipv4", "supernet_ipv6"],
        ).get()

        self.assertEqual(server_q["supernet_ipv4"], network_ipv4["hostname"])
        self.assertEqual(server_q["supernet_ipv6"], network_ipv6["hostname"])

    def test_af_aware_unaware_supernet(self):
        # AF-aware and unaware supernets can be used together.

        rn = self._get_server("route_network")
        rn["intern_ip"] = "192.0.2.0/24"
        rn["ip_config_ipv4"] = "192.0.2.0/24"
        rn["ip_config_ipv6"] = "2001:db8::/64"
        rn.commit(user=User.objects.first())

        pn_ipv4 = self._get_server("provider_network")
        pn_ipv4["intern_ip"] = "192.0.2.0/24"
        pn_ipv4["ip_config_ipv4"] = "192.0.2.0/24"
        pn_ipv4.commit(user=User.objects.first())

        pn_ipv6 = self._get_server("provider_network")
        pn_ipv6["intern_ip"] = "2001:db8::/64"
        pn_ipv6["ip_config_ipv6"] = "2001:db8::/64"
        pn_ipv6.commit(user=User.objects.first())

        server = self._get_server("host")
        server["intern_ip"] = "192.0.2.1"
        server["ip_config_ipv4"] = "192.0.2.1"
        server["ip_config_ipv6"] = "2001:db8::1"
        server.commit(user=User.objects.first())

        server_q = Query(
            {"hostname": server["hostname"]},
            ["supernet_no_af", "supernet_ipv4", "supernet_ipv6"],
        ).get()

        self.assertEqual(server_q["supernet_no_af"], rn["hostname"])
        self.assertEqual(server_q["supernet_ipv4"], pn_ipv4["hostname"])
        self.assertEqual(server_q["supernet_ipv6"], pn_ipv6["hostname"])


class TestIpAddrTypeHostForSupernetQuery(TestIpAddrType):
    def setUp(self):
        super().setUp()
        self.pn_ipv4 = self._get_server("provider_network")
        self.pn_ipv4["intern_ip"] = "192.0.2.0/24"
        self.pn_ipv4["ip_config_ipv4"] = "192.0.2.0/24"
        self.pn_ipv4["network_type_ipv4"] = "public_ipv4"
        self.pn_ipv4.commit(user=User.objects.first())
        
        self.rn_ipv4 = self._get_server("route_network")
        self.rn_ipv4["intern_ip"] = "192.0.2.0/28"
        self.rn_ipv4["ip_config_ipv4"] = "192.0.2.0/28"
        self.rn_ipv4["network_type"] = "internal_ipv4"
        self.rn_ipv4.commit(user=User.objects.first())

        self.pn_ipv6 = self._get_server("provider_network")
        self.pn_ipv6["intern_ip"] = "2001:db8::/64"
        self.pn_ipv6["ip_config_ipv6"] = "2001:db8::/64"
        self.pn_ipv6["network_type_ipv6"] = "internal_ipv6"
        self.pn_ipv6.commit(user=User.objects.first())

        self.rn_ipv6 = self._get_server("route_network")
        self.rn_ipv6["intern_ip"] = "2001:db8::0010/124"
        self.rn_ipv6["ip_config_ipv6"] = "2001:db8::0010/124"
        self.rn_ipv6["network_type"] = "internal_ipv6"
        self.rn_ipv6.commit(user=User.objects.first())

        self.server_pn = self._get_server("host")
        self.server_pn["intern_ip"] = "192.0.2.17"
        self.server_pn["ip_config_ipv4"] = "192.0.2.17"
        self.server_pn["ip_config_ipv6"] = "2001:db8::0021"
        self.server_pn.commit(user=User.objects.first())

        self.server_rn = self._get_server("host")
        self.server_rn["intern_ip"] = "192.0.2.1"
        self.server_rn["ip_config_ipv4"] = "192.0.2.1"
        self.server_rn["ip_config_ipv6"] = "2001:db8::0011"
        self.server_rn.commit(user=User.objects.first())


    def test_af_unaware_supernet(self):
        # Query a related attribute over an AF-unaware supernet
        #
        # Warning:
        # Since we're querying AF-unaware attribute, the server can belong to multiple
        # networks over IPv4 and IPv6 inet attributes. But since the supernet attribute
        # is a single-attribute, only one of those networks is returned.

        server_q = Query(
            {"supernet_no_af": self.rn_ipv4["hostname"], "servertype": "host"},
            ["hostname", "supernet_no_af"],
        ).get()
        self.assertIn(
            server_q["supernet_no_af"],
            (self.rn_ipv4["hostname"], self.rn_ipv6["hostname"]),
        )

        server_q = Query(
            {"supernet_no_af": self.rn_ipv6["hostname"], "servertype": "host"},
            ["hostname", "supernet_no_af"],
        ).get()
        self.assertIn(
            server_q["supernet_no_af"],
            (self.rn_ipv4["hostname"], self.rn_ipv6["hostname"]),
        )

    def test_af_unaware_supernet_related(self):
        # Query a related attribute over an AF-unaware supernet
        #
        # Warning:
        # Since we're querying AF-unaware attribute, the server can belong to multiple
        # networks over IPv4 and IPv6 inet attributes. But since the supernet attribute
        # is a single-attribute, only one of those networks is returned.

        server_q = Query(
            {"network_type": "internal_ipv4", "servertype": "host"},
            ["hostname", "supernet_no_af"],
        ).get()
        self.assertIn(
            server_q["supernet_no_af"],
            (self.rn_ipv4["hostname"], self.rn_ipv6["hostname"]),
        )

        server_q = Query(
            {"network_type": "internal_ipv6", "servertype": "host"},
            ["hostname", "supernet_no_af"],
        ).get()
        self.assertIn(
            server_q["supernet_no_af"],
            (self.rn_ipv4["hostname"], self.rn_ipv6["hostname"]),
        )

    def test_related_attribute_without_servertype_filter(self):
        # Filtering on an attribute that some servertypes carry directly and
        # others inherit, without narrowing the servertype, makes the SQL
        # generator emit one EXISTS per relation path (see
        # sql_generator._real_condition_sql).  Both paths have to deliver:
        # the route networks match directly, server_rn through its
        # AF-unaware supernet.  server_pn sits in no route network.
        hostnames = {
            server["hostname"]
            for server in Query(
                {
                    "network_type": filters.Any(
                        "internal_ipv4", "internal_ipv6"
                    ),
                },
                ["hostname"],
            )
        }
        self.assertEqual(
            hostnames,
            {
                self.rn_ipv4["hostname"],
                self.rn_ipv6["hostname"],
                self.server_rn["hostname"],
            },
        )

    def test_af_aware_supernet(self):
        # Querying for AF-aware supernet attribute will find only objects
        # matching the given address family.

        server_q = list(Query(
            {"supernet_ipv4": self.pn_ipv4["hostname"], "servertype": "host"},
            ["hostname", "supernet_ipv4", "ip_config_ipv4"],
            ["ip_config_ipv4"]
        ))
        self.assertEqual(len(server_q), 2)
        self.assertEqual(server_q[0]["hostname"], self.server_rn["hostname"])
        self.assertEqual(server_q[0]["supernet_ipv4"], self.pn_ipv4["hostname"])
        self.assertEqual(server_q[1]["hostname"], self.server_pn["hostname"])
        self.assertEqual(server_q[1]["supernet_ipv4"], self.pn_ipv4["hostname"])

        # Test that af_q is correctly applied in _condition_sql
        with self.assertRaises(DatasetError):
            server_q = Query(
                {"supernet_ipv4": self.pn_ipv6["hostname"], "servertype": "host"},
                ["hostname", "supernet_ipv4"],
            ).get()
        with self.assertRaises(DatasetError):
            server_q = Query(
                {"supernet_ipv6": self.pn_ipv4["hostname"], "servertype": "host"},
                ["hostname", "supernet_ipv6"],
            ).get()

    def test_af_aware_supernet_related(self):
        # Query a related attribute over an AF-aware supernet

        server_q = list(Query(
            {"network_type_ipv4": "public_ipv4", "servertype": "host"},
            ["hostname", "ip_config_ipv4", "network_type_ipv4", "network_type_ipv6"],
            ["ip_config_ipv4"],
        ))
        self.assertEqual(len(server_q), 2)
        self.assertEqual(server_q[0]["hostname"], self.server_rn["hostname"])
        self.assertEqual(server_q[0]["network_type_ipv4"], self.pn_ipv4["network_type_ipv4"])
        self.assertEqual(server_q[1]["hostname"], self.server_pn["hostname"])
        self.assertEqual(server_q[1]["network_type_ipv4"], self.pn_ipv4["network_type_ipv4"])

        with self.assertRaises(DatasetError):
            server_q = Query(
                {"supernet_ipv6": self.pn_ipv4["network_type_ipv4"], "servertype": "host"},
                ["hostname", "supernet_ipv6", "ip_config_ipv6"],
                ["ip_config_ipv6"]
            ).get()

        # Test that af_q is correctly applied in _real_condition_sql
        with self.assertRaises(DatasetError):
            server_q = Query(
                {"network_type_ipv4": "public_ipv6", "servertype": "host"},
                ["hostname", "network_type_ipv4", "network_type_ipv6"],
            ).get()
        with self.assertRaises(DatasetError):
            server_q = Query(
                {"network_type_ipv6": "public_ipv4", "servertype": "host"},
                ["hostname", "network_type_ipv4", "network_type_ipv6"],
            ).get()

class TestIpAddrTypeContainment(TestIpAddrType):
    def setUp(self):
        super().setUp()
        self.network_1 = self._get_server("provider_network")
        self.network_1["intern_ip"] = "2001:db8::/64"
        self.network_1["ip_config_ipv6"] = "2001:db8::/64"
        self.network_1.commit(user=User.objects.first())

        self.network_2 = self._get_server("route_network")
        self.network_2["intern_ip"] = "2001:db8::0010/124"
        self.network_2["ip_config_ipv6"] = "2001:db8::0010/124"
        self.network_2.commit(user=User.objects.first())

        self.server_1 = self._get_server("host")
        self.server_1["intern_ip"] = "2001:db8::0011"
        self.server_1["ip_config_ipv6"] = "2001:db8::0011"
        self.server_1.commit(user=User.objects.first())

        self.server_2 = self._get_server("host")
        self.server_2["intern_ip"] = "2001:db8::0021"
        self.server_2["ip_config_ipv6"] = "2001:db8::0021"
        self.server_2.commit(user=User.objects.first())

    # I honestly don't understand what inet.startswith() is supposed to do")
    #def test_startswith(self):
    #    pass
    def test_contains(self):
        network_q = list(Query(
            {"ip_config_ipv6": filters.Contains("2001:db8::0021")},
            ["hostname", "servertype", "ip_config_ipv6"],
            ["ip_config_ipv6"],
        ))
        self.assertEqual(len(network_q), 2)
        self.assertEqual(network_q[0]["hostname"], self.network_1["hostname"])
        self.assertEqual(network_q[1]["hostname"], self.server_2["hostname"])

    def test_containedby(self):
        network_q = list(Query(
            {"ip_config_ipv6": filters.ContainedBy("2001:db8::0000/120")},
            ["hostname", "servertype", "ip_config_ipv6"],
            ["ip_config_ipv6"],
        ))

        self.assertEqual(len(network_q), 3)
        self.assertEqual(network_q[0]["hostname"], self.network_2["hostname"])
        self.assertEqual(network_q[1]["hostname"], self.server_1["hostname"])
        self.assertEqual(network_q[2]["hostname"], self.server_2["hostname"])

    def test_containedonlyby(self):
        # ContainedOnlyBy means find objects contained by given prefix
        # apart from the ones contained by another object.
        network_q = list(Query(
            {"ip_config_ipv6": filters.ContainedOnlyBy("2001:db8::0000/120")},
            ["hostname", "servertype", "ip_config_ipv6"],
            ["ip_config_ipv6"],
        ))
        self.assertEqual(len(network_q), 2)
        self.assertEqual(network_q[0]["hostname"], self.network_2["hostname"])
        self.assertEqual(network_q[1]["hostname"], self.server_2["hostname"])

class TestIpAddrTypeSupernetFilter(TestIpAddrType):
    """Filter on a supernet attribute without narrowing the servertype

    The SQL generator renders such a filter as an uncorrelated subquery that
    matches the networks by hostname and selects the servers with an address
    inside them (see sql_generator._supernet_server_ids_sql).  The networks
    get deterministic hostnames so the regexp of a real-world query can be
    used as is.  Route networks must not overlap, hence one /64 each.
    """

    NETWORKS = {
        "servers1-officeh-int": "2001:db8:1::/64",
        "servers2-officeh-int": "2001:db8:2::/64",
        "servers3-officeb-int": "2001:db8:3::/64",
    }
    HOSTS = {
        "host-1": "2001:db8:1::1",
        "host-2": "2001:db8:2::1",
        "host-3": "2001:db8:3::1",
        "host-9": "2001:db8:9::1",  # In no route network
    }

    def setUp(self):
        super().setUp()
        for hostname, network in self.NETWORKS.items():
            server = Query().new_object("route_network")
            server["hostname"] = hostname
            server["intern_ip"] = network
            server["ip_config_ipv6"] = network
            server.commit(user=User.objects.first())

        for hostname, address in self.HOSTS.items():
            server = Query().new_object("host")
            server["hostname"] = hostname
            server["intern_ip"] = address
            server["ip_config_ipv6"] = address
            server.commit(user=User.objects.first())

    def _hostnames(self, supernet_filter):
        return {
            server["hostname"]
            for server in Query({"supernet_no_af": supernet_filter}, ["hostname"])
        }

    def test_regexp(self):
        self.assertEqual(
            self._hostnames(filters.Regexp("servers[0-9]+-officeh-int")),
            {"host-1", "host-2"},
        )

    def test_not_regexp(self):
        # The subquery selects a NOT NULL column, so NOT IN keeps set
        # semantics: the servers inside a matching network drop out, the
        # others stay in, including the one in no network at all.
        hostnames = self._hostnames(
            filters.Not(filters.Regexp("servers[0-9]+-officeh-int"))
        )
        self.assertNotIn("host-1", hostnames)
        self.assertNotIn("host-2", hostnames)
        self.assertIn("host-3", hostnames)
        self.assertIn("host-9", hostnames)

    def test_equals(self):
        self.assertEqual(self._hostnames("servers2-officeh-int"), {"host-2"})

    def test_any(self):
        # Several plain values get collected into one "IN (...)" on the
        # supernet hostname, see sql_generator._logical_filter_sql_condition.
        self.assertEqual(
            self._hostnames(
                filters.Any("servers1-officeh-int", "servers3-officeb-int")
            ),
            {"host-1", "host-3"},
        )

    def test_empty(self):
        hostnames = self._hostnames(filters.Empty())
        self.assertIn("host-9", hostnames)
        self.assertNotIn("host-1", hostnames)

    def test_with_servertype_filter(self):
        # The query from the field: a regexp on the supernet attribute
        # combined with an explicit servertype restriction.
        hostnames = {
            server["hostname"]
            for server in Query(
                {
                    "supernet_no_af": filters.Regexp("officeh-int"),
                    "servertype": "host",
                },
                ["hostname"],
            )
        }
        self.assertEqual(hostnames, {"host-1", "host-2"})

    def test_generated_sql_shape(self):
        # Guard the shape the tests above rely on: the hostname condition
        # sits directly on the "supernet" alias instead of going through a
        # sublink on the server table, and nothing correlates the subquery
        # to the outer "server".
        sql = get_server_query(
            [(Attribute.objects.get(pk="supernet_no_af"), filters.Regexp("x"))],
            {},
        )
        self.assertIn("supernet.hostname::text ~ E'x'", sql)
        self.assertNotIn("SELECT server_id FROM server", sql)
        self.assertNotIn("= server.server_id", sql)

    def test_explain_uses_inet_gist_index(self):
        # The point of the uncorrelated shape: Postgres can drive the
        # containment join through the GiST index on
        # server_inet_attribute.value.  On tables as small as the test
        # fixture the planner prefers a sequential scan over any index, so
        # rule that out for the EXPLAIN.  This does not prove the planner
        # picks the index unaided, only that the query lets it, which the
        # correlated EXISTS of before did not.
        sql = get_server_query(
            [(
                Attribute.objects.get(pk="supernet_no_af"),
                filters.Regexp("servers[0-9]+-officeh-int"),
            )],
            {},
        )
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute("EXPLAIN " + sql)
            plan = "\n".join(row[0] for row in cursor.fetchall())

        self.assertIn("server_inet_attribute_value_idx", plan, plan)


class TestIpAddrTypeTwoSupernetFilters(TestIpAddrType):
    """Filter on two supernet attributes of different target servertypes

    Each supernet filter becomes its own "server_id IN (SELECT ...)"
    subquery, so a query on both a provider network and a route network
    has to intersect the two sets.  The supernet_filter fixture mirrors the
    layout in the field: provider networks containing route networks
    containing hosts.  One host sits in a provider network but in no route
    network.
    """

    fixtures = TestIpAddrType.fixtures + ["supernet_filter.json"]

    def _hostnames(self, **filters_):
        # supernet_ipv6 targets provider_network, supernet_no_af targets
        # route_network, see the ip_addr_type fixture.
        return {
            server["hostname"]
            for server in Query(filters_, ["hostname"])
        }

    def test_provider_network_only(self):
        self.assertEqual(
            self._hostnames(supernet_ipv6="office1"),
            {"host-net1-office1", "host-net2-office1", "host-office1"},
        )

    def test_route_network_only(self):
        self.assertEqual(
            self._hostnames(supernet_no_af="net1-office1-int"),
            {"host-net1-office1"},
        )

    def test_both_matching(self):
        self.assertEqual(
            self._hostnames(
                supernet_ipv6="office1", supernet_no_af="net1-office1-int"
            ),
            {"host-net1-office1"},
        )

    def test_contradicting(self):
        # The route network lies in the other provider network, so the two
        # subqueries have no server in common.
        self.assertEqual(
            self._hostnames(
                supernet_ipv6="office2", supernet_no_af="net1-office1-int"
            ),
            set(),
        )

    def test_regexp_on_both(self):
        self.assertEqual(
            self._hostnames(
                supernet_ipv6=filters.Regexp("^office[0-9]$"),
                supernet_no_af=filters.Regexp("^net1-"),
            ),
            {"host-net1-office1", "host-net1-office2"},
        )

    def test_any_and_not(self):
        # Narrow to office1 and drop one of its route networks.  The host in
        # no route network stays, as the negated subquery keeps set
        # semantics (see TestIpAddrTypeSupernetFilter.test_not_regexp).
        self.assertEqual(
            self._hostnames(
                supernet_ipv6=filters.Any("office1"),
                supernet_no_af=filters.Not("net1-office1-int"),
            ),
            {"host-net2-office1", "host-office1"},
        )

    def test_with_servertype_filter(self):
        self.assertEqual(
            self._hostnames(
                supernet_ipv6="office2",
                supernet_no_af="net2-office2-int",
                servertype="host",
            ),
            {"host-net2-office2"},
        )
