"""Serveradmin - Query Materializer

Copyright (c) 2019 InnoGames GmbH
"""

# XXX: This module is pretty complicated even though the functions are not
# on their own.  They store a lot of stuff on the object.  It is probably
# a good idea to refactor this by using more top level functions instead of
# object methods.

import logging

from ipaddress import IPv4Address, IPv6Address
from adminapi.dataset import DatasetObject
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ServerAttribute,
    ServerRelationAttribute, ServerInetAttribute,
)

logger = logging.getLogger(__package__)


class QueryMaterializer:
    def __init__(self, servers, joined_attributes, order_by_attributes=[]):
        self._servers = servers
        self._joined_attributes = joined_attributes
        self._order_by_attributes = order_by_attributes
        # XXX: Optimize this query out
        self._servertype_lookup = {
            servertype.servertype_id: servertype
            for servertype in Servertype.objects.all()
        }

        self._server_attributes = {}
        servers_by_type = {}
        for server in self._servers:
            self._server_attributes[server] = {
                Attribute.specials["object_id"]: server.server_id,
                Attribute.specials["hostname"]: server.hostname,
                Attribute.specials["intern_ip"]: server.intern_ip,
                Attribute.specials["servertype"]: server.servertype_id,
            }
            servers_by_type.setdefault(server.servertype_id, []).append(server)

        self._select_attributes(servers_by_type.keys())
        self._initialize_attributes(servers_by_type)
        self._add_attributes(servers_by_type)
        self._add_related_attributes(servers_by_type)

    def __iter__(self):
        servers = self._servers
        if self._order_by_attributes:

            def order_by_key(key):
                return tuple(
                    self._get_order_by_attribute(key, a)
                    for a in self._order_by_attributes
                )

            servers = sorted(servers, key=order_by_key)

        join_results = self._get_join_results()
        return (
            DatasetObject(self._get_attributes(s, join_results), s.server_id)
            for s in servers
        )

    def _select_attributes(self, servertype_ids):
        self._attributes_by_type = {}
        self._servertype_ids_by_attribute = {}
        self._related_servertype_attributes = []
        attributes = {a.attribute_id: a for a in self._joined_attributes}
        for sa in ServertypeAttribute.objects.filter(
            servertype_id__in=servertype_ids,
            attribute__in=self._joined_attributes,
        ):
            attribute = attributes[sa.attribute_id]
            self._select_servertype_attribute(attribute, sa)

    def _select_servertype_attribute(self, attribute, sa):
        self._attributes_by_type.setdefault(attribute.type, set()).add(attribute)
        self._servertype_ids_by_attribute.setdefault(attribute, []).append(
            sa.servertype_id
        )

        related_via_attribute_id = sa.related_via_attribute_id
        if related_via_attribute_id:
            # TODO: Order the list in a way to support recursive related
            # attributes.
            self._related_servertype_attributes.append((attribute, sa))

            # If we have related attributes in the attribute list, we have
            # to add the relations in there, too.  We are going to use
            # those to query the related attributes.
            # TODO: Optimize this to avoid recursion and selecting related
            # attribute in here
            sa = (
                ServertypeAttribute.objects.filter(
                    servertype_id=sa.servertype_id,
                    attribute_id=related_via_attribute_id,
                )
                .prefetch_related("attribute")
                .get()
            )
            self._select_servertype_attribute(sa.attribute, sa)

    def _initialize_attributes(self, servers_by_type):
        for attribute, servertype_ids in self._servertype_ids_by_attribute.items():
            init = attribute.initializer()
            for servertype_id in servertype_ids:
                for server in servers_by_type[servertype_id]:
                    self._server_attributes[server][attribute] = init()

    def _add_attributes(self, servers_by_type):
        """Add the attributes to the results"""
        for key, attributes in self._attributes_by_type.items():
            if key == "supernet":
                for attribute in attributes:
                    self._add_supernet_attribute(
                        attribute,
                        (
                            s
                            for st in self._servertype_ids_by_attribute[attribute]
                            for s in servers_by_type[st]
                        ),
                    )
            elif key == "domain":
                for attribute in attributes:
                    self._add_domain_attribute(
                        attribute,
                        [
                            s
                            for st in self._servertype_ids_by_attribute[attribute]
                            for s in servers_by_type[st]
                        ],
                    )
            elif key == "reverse":
                reversed_attributes = {a.reversed_attribute_id: a for a in attributes}
                for sa in (
                    ServerRelationAttribute.objects.filter(
                        value_id__in=self._server_attributes.keys(),
                        attribute_id__in=reversed_attributes.keys(),
                    )
                    .prefetch_related("server")
                    .defer(
                        "server__intern_ip",
                        "server__servertype",
                    )
                ):
                    self._add_attribute_value(
                        sa.value,
                        reversed_attributes[sa.attribute_id],
                        sa.server,
                    )
            else:
                attribute_lookup = {a.attribute_id: a for a in attributes}
                for sa in (
                    ServerAttribute.get_model(key)
                    .objects.filter(
                        server__in=self._server_attributes.keys(),
                        attribute__in=attributes,
                    )
                    .prefetch_related("server")
                    .defer(
                        "server__intern_ip",
                        "server__servertype",
                    )
                ):
                    self._add_attribute_value(
                        sa.server,
                        attribute_lookup[sa.attribute_id],
                        sa.get_value(),
                    )

    def _add_related_attributes(self, servers_by_type):
        for attribute, sa in self._related_servertype_attributes:
            self._add_related_attribute(attribute, sa, servers_by_type)

    def _add_domain_attribute(self, attribute, servers):
        domain_names = {s.hostname.split(".", 1)[-1] for s in servers}
        domain_lookup = {
            domain.hostname: domain
            for domain in Server.objects.filter(
                servertype=attribute.target_servertype,
                hostname__in=domain_names,
            )
        }

        for server in servers:
            self._server_attributes[server][attribute] = domain_lookup.get(
                server.hostname.split(".", 1)[-1]
            )

    def _add_supernet_attribute(self, attribute: Attribute, servers_in):
        """Calculate the supernet attribute of given servers

        Get inet attributes of given servers_in (call them hosts), narrow them down to
        given address family if required. For every attribute found, get inet attributes
        of servers of given servertype and those servers (call them nets), so that
        the host's IP address or prefix fits within the net's IP address or prefix.
        """

        q = f"""
            SELECT
                net.server_id,
                net.hostname,
                net.intern_ip,
                net.servertype_id,
                net_attr.inet_address_family,
                host_attr.inet_address_family,
                host.server_id AS host_server_id,
                host_attr.attribute_id AS host_attr_name
            FROM server AS host
            JOIN {ServerInetAttribute._meta.db_table} AS host_addr ON (host.server_id = host_addr.server_id)
            JOIN {ServerInetAttribute._meta.db_table} AS net_addr ON (host_addr.value <<= net_addr.value AND host_addr.attribute_id = net_addr.attribute_id)
            JOIN {Server._meta.db_table} AS net ON (net_addr.server_id = net.server_id)
            JOIN {Attribute._meta.db_table} AS net_attr ON (net_attr.attribute_id = net_addr.attribute_id)
            JOIN {Attribute._meta.db_table} AS host_attr ON (host_attr.attribute_id = host_addr.attribute_id)
            WHERE
                net.servertype_id = %(target_servertype)s
                AND host.server_id = any(%(hosts)s)
        """

        if attribute.inet_address_family:
            q += """
                AND net_attr.inet_address_family = %(address_family)s
                AND host_attr.inet_address_family = %(address_family)s
            """

        servers_by_id = {s.server_id: s for s in servers_in}

        supernets = Server.objects.raw(
            q,
            {
                "target_servertype": attribute.target_servertype_id,
                "address_family": attribute.inet_address_family,
                "hosts": list(servers_by_id.keys()),
            },
            translations={
                "net.server_id": "server_id",
                "net.hostname": "hostname",
                "net.intern_ip": "intern_ip",
                "net.servertype_id": "servertype_id",
            },
        )
        for cur_supernet in supernets:
            cur_server = servers_by_id[cur_supernet.host_server_id]
            prev_supernet = self._server_attributes.get(cur_server, {}).get(attribute)
            if prev_supernet and prev_supernet != cur_supernet:
                # TODO: Raise an exception once all data is cleaned up and conflicting
                # AF-unaware attributes are removed.
                logger.warning(
                    f"Conflicting supernet {attribute} for {cur_server.hostname}: "
                    f"{prev_supernet.host_attr_name}->{prev_supernet} vs {cur_supernet.host_attr_name}->{cur_supernet}"
                )
            self._server_attributes[cur_server][attribute] = cur_supernet

    def _add_related_attribute(self, attribute, servertype_attribute, servers_by_type):
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related = {}
        for target in servers_by_type[servertype_attribute.servertype_id]:
            attributes = self._server_attributes[target]
            if related_via_attribute in attributes:
                if related_via_attribute.multi:
                    for source in attributes[related_via_attribute]:
                        servers_by_related.setdefault(source, []).append(target)
                else:
                    source = attributes[related_via_attribute]
                    servers_by_related.setdefault(source, []).append(target)

        # Then, query and set the related attributes
        for sa in (
            ServerAttribute.get_model(attribute.type)
            .objects.filter(
                server__hostname__in=servers_by_related.keys(),
                attribute=attribute,
            )
            .prefetch_related("server")
            .defer(
                "server__intern_ip",
                "server__servertype",
            )
        ):
            for target in servers_by_related[sa.server]:
                self._add_attribute_value(target, attribute, sa.get_value())

    def _add_attribute_value(self, server, attribute, value):
        if attribute.multi:
            try:
                self._server_attributes[server][attribute].add(value)
            except KeyError:
                # If the attribute is removed from the servertype but
                # left on the servers, this error would occur.  It is not
                # really expected, but we don't want to crash either.
                pass
        else:
            self._server_attributes[server][attribute] = value

    def _get_order_by_attribute(self, server, attribute):
        """Return a tuple to sort items by the key

        We want the servers which doesn't have the attribute at all
        to appear at last, the server which the attribute is not set
        to appear in the beginning, and the rest in between.  Keep in
        mind that some datatypes are not sortable with each other, some
        not even with None, so we have to so something in here.
        """
        if attribute not in self._server_attributes[server]:
            return 1, None
        value = self._server_attributes[server][attribute]
        if value is None:
            return -1, None
        if attribute.multi:
            return 0, tuple(_sort_key(v) for v in value)
        return 0, _sort_key(value)

    def _get_attributes(self, server, join_results):  # NOQA: C901
        servertype = self._servertype_lookup[server.servertype_id]
        server_attributes = self._server_attributes[server]
        for attribute, value in server_attributes.items():
            if attribute not in self._joined_attributes:
                continue

            if attribute.type == "inet":
                if value is None:
                    yield attribute.attribute_id, None
                else:
                    if servertype.ip_addr_type in ("host", "loadbalancer"):
                        yield attribute.attribute_id, value.ip
                    else:
                        assert servertype.ip_addr_type == "network"
                        yield attribute.attribute_id, value.network
            elif value is None:
                yield attribute.attribute_id, None
            elif attribute in join_results:
                if attribute.multi:
                    yield attribute.attribute_id, [
                        join_results[attribute][v] for v in value
                    ]
                else:
                    yield (attribute.attribute_id, join_results[attribute][value])
            elif attribute.multi:
                yield attribute.attribute_id, {
                    v.hostname if isinstance(v, Server) else v for v in value
                }
            elif isinstance(value, Server):
                yield attribute.attribute_id, value.hostname
            else:
                yield attribute.attribute_id, value

    def _get_join_results(self):
        results = dict()
        for attribute, joined_attributes in self._joined_attributes.items():
            if joined_attributes is None:
                continue

            servers = self._get_servers_to_join(attribute)
            server_objs = type(self)(servers, joined_attributes)
            results[attribute] = dict(zip(servers, server_objs))

        return results

    def _get_servers_to_join(self, attribute):
        servers = set()
        for server_attributes in self._server_attributes.values():
            if attribute in server_attributes:
                value = server_attributes[attribute]
                if value is None:
                    continue

                if attribute.multi:
                    for server in value:
                        servers.add(server)
                else:
                    servers.add(value)

        return servers


def _sort_key(value):
    if isinstance(value, (IPv4Address, IPv6Address)):
        return value.version, value
    if isinstance(value, Server):
        return value.hostname
    return value


def get_default_attribute_values(servertype_id):
    servertype = Servertype.objects.get(servertype_id=servertype_id)
    attribute_values = {}

    for attribute_id in Attribute.specials:
        if attribute_id == "servertype":
            value = servertype_id
        else:
            value = None
        attribute_values[attribute_id] = value

    for sa in servertype.attributes.all():
        attribute_values[sa.attribute_id] = sa.get_default_value()

    return attribute_values
