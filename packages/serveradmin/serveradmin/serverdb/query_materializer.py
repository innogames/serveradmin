"""Serveradmin - Query Materializer

Copyright (c) 2019 InnoGames GmbH
"""

# XXX: This module is pretty complicated even though the functions are not
# on their own.  They store a lot of stuff on the object.  It is probably
# a good idea to refactor this by using more top level functions instead of
# object methods.

import logging

from ipaddress import IPv4Address, IPv6Address

from django.db import connection
from django.db.models import Prefetch

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


def _server_prefetch():
    """Prefetch "server" without loading the expensive intern_ip column

    prefetch_related() issues its own query, built from Server._base_manager
    (see ForwardManyToOneDescriptor.get_prefetch_querysets), so a
    defer("server__intern_ip") on the outer queryset never reaches it - that
    spelling only takes effect for select_related() traversals.  Passing an
    explicit queryset is the only way to actually defer the column here.

    It is worth deferring because netfields runs every inet value through
    ipaddress.ip_interface(), which is pure Python and showed up as roughly a
    quarter of the profile of a large query - even though intern_ip is not a
    real attribute and is never part of a restrict clause.

    Only intern_ip is deferred.  servertype_id is a plain varchar with no
    converter, so deferring it saves nothing while risking a query per object
    for anything that reads it.
    """
    return Prefetch('server', queryset=Server._base_manager.defer('intern_ip'))


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

        # Keyed by server_id, not by the Server instance.  Model.__hash__()
        # is a Python-level call that goes through _is_pk_set() and the pk
        # property, and this map is looked up once per server per attribute -
        # over a million times on a large query.  Plain ints hash in C.
        self._server_attributes = {}
        servers_by_type = {}
        for server in self._servers:
            self._server_attributes[server.server_id] = {
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
                    self._server_attributes[server.server_id][attribute] = init()

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
                    # Unlike the other branches, sa.server is stored as an
                    # attribute *value* here, so it can escape into the
                    # results and reach _get_servers_to_join(), which reads
                    # intern_ip.  Deferring it would cost a query per object,
                    # so this one deliberately keeps the whole row.
                    .prefetch_related("server")
                ):
                    self._add_attribute_value(
                        sa.value_id,
                        reversed_attributes[sa.attribute_id],
                        sa.server,
                    )
            else:
                attribute_lookup = {a.attribute_id: a for a in attributes}
                for sa in (
                    ServerAttribute.get_model(key)
                    .objects.filter(
                        server_id__in=self._server_attributes.keys(),
                        attribute__in=attributes,
                    )
                ):
                    self._add_attribute_value(
                        sa.server_id,
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
                servertype__in=attribute.target_servertype.all(),
                hostname__in=domain_names,
            )
        }

        for server in servers:
            self._server_attributes[server.server_id][attribute] = domain_lookup.get(
                server.hostname.split(".", 1)[-1]
            )

    def _add_supernet_attribute(self, attribute: Attribute, servers_in):
        """Calculate the supernet attribute of given servers

        Get inet attributes of given servers_in (call them hosts), narrow them down to
        given address family if required. For every attribute found, get inet attributes
        of servers of given servertype and those servers (call them nets), so that
        the host's IP address or prefix fits within the net's IP address or prefix.
        """

        # Only ids are selected.  This join yields one row per (host, net)
        # pair - tens of thousands of them on a large query - while the
        # distinct nets they point at number far fewer.  Reading the net rows
        # through Server.objects.raw() therefore built one model instance per
        # row, each parsing net.intern_ip through netfields, rather than one
        # per distinct net.  The two inet_address_family columns this used to
        # select were never read at all.
        q = f"""
            SELECT
                net.server_id AS net_server_id,
                host.server_id AS host_server_id,
                host_attr.attribute_id AS host_attr_name
            FROM server AS host
            JOIN {ServerInetAttribute._meta.db_table} AS host_addr ON (host.server_id = host_addr.server_id)
            JOIN {ServerInetAttribute._meta.db_table} AS net_addr ON (host_addr.value <<= net_addr.value AND host_addr.attribute_id = net_addr.attribute_id)
            JOIN {Server._meta.db_table} AS net ON (net_addr.server_id = net.server_id)
            JOIN {Attribute._meta.db_table} AS net_attr ON (net_attr.attribute_id = net_addr.attribute_id)
            JOIN {Attribute._meta.db_table} AS host_attr ON (host_attr.attribute_id = host_addr.attribute_id)
            WHERE
                net.servertype_id = ANY(%(target_servertypes)s)
                AND host.server_id = any(%(hosts)s)
        """

        if attribute.inet_address_family:
            q += """
                AND net_attr.inet_address_family = %(address_family)s
                AND host_attr.inet_address_family = %(address_family)s
            """

        servers_by_id = {s.server_id: s for s in servers_in}

        with connection.cursor() as cursor:
            cursor.execute(q, {
                "target_servertypes": list(
                    attribute.target_servertype.values_list(
                        'servertype_id', flat=True
                    )
                ),
                "address_family": attribute.inet_address_family,
                "hosts": list(servers_by_id.keys()),
            })
            rows = cursor.fetchall()

        # The nets are fetched whole, intern_ip included: they are stored as
        # attribute values and can reach a nested QueryMaterializer through
        # _get_servers_to_join(), which reads it.
        supernets = {
            net.server_id: net
            for net in Server.objects.filter(
                server_id__in={r[0] for r in rows}
            )
        }

        # Which host attribute produced the supernet currently stored for a
        # host.  This used to be read back off the supernet object itself,
        # which is no longer possible now that one net object is shared by
        # every host sitting in it.
        via_attribute_ids = {}
        for net_server_id, host_server_id, host_attr_name in rows:
            cur_supernet = supernets[net_server_id]
            prev_supernet = (
                self._server_attributes.get(host_server_id, {}).get(attribute)
            )
            if prev_supernet and prev_supernet != cur_supernet:
                # TODO: Raise an exception once all data is cleaned up and conflicting
                # AF-unaware attributes are removed.
                logger.warning(
                    f"Conflicting supernet {attribute} for "
                    f"{servers_by_id[host_server_id].hostname}: "
                    f"{via_attribute_ids.get(host_server_id)}->{prev_supernet} vs "
                    f"{host_attr_name}->{cur_supernet}"
                )
            self._server_attributes[host_server_id][attribute] = cur_supernet
            via_attribute_ids[host_server_id] = host_attr_name

    def _add_related_attribute(self, attribute, servertype_attribute, servers_by_type):
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related = {}
        for target in servers_by_type[servertype_attribute.servertype_id]:
            attributes = self._server_attributes[target.server_id]
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
            .prefetch_related(_server_prefetch())
        ):
            for target in servers_by_related[sa.server]:
                self._add_attribute_value(
                    target.server_id, attribute, sa.get_value()
                )

    def _add_attribute_value(self, server_id, attribute, value):
        if attribute.multi:
            try:
                self._server_attributes[server_id][attribute].add(value)
            except KeyError:
                # If the attribute is removed from the servertype but
                # left on the servers, this error would occur.  It is not
                # really expected, but we don't want to crash either.
                pass
        else:
            self._server_attributes[server_id][attribute] = value

    def _get_order_by_attribute(self, server, attribute):
        """Return a tuple to sort items by the key

        We want the servers which doesn't have the attribute at all
        to appear at last, the server which the attribute is not set
        to appear in the beginning, and the rest in between.  Keep in
        mind that some datatypes are not sortable with each other, some
        not even with None, so we have to so something in here.
        """
        server_attributes = self._server_attributes[server.server_id]
        if attribute not in server_attributes:
            return 1, None
        value = server_attributes[attribute]
        if value is None:
            return -1, None
        if attribute.multi:
            return 0, tuple(_sort_key(v) for v in value)
        return 0, _sort_key(value)

    def _get_attributes(self, server, join_results):  # NOQA: C901
        servertype = self._servertype_lookup[server.servertype_id]
        server_attributes = self._server_attributes[server.server_id]
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
