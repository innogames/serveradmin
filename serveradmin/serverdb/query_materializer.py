# XXX: This module is pretty complicated even though the functions are not
# on their own.  They store a lot of stuff on the object.  It is probably
# a good idea to refactor this by using more top level functions instead of
# object methods.

from collections import defaultdict
from ipaddress import IPv4Address, IPv6Address

from serveradmin.serverdb.models import (
    Project,
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ServerAttribute,
    ServerHostnameAttribute,
)


class QueryMaterializer:
    def __init__(self, servers, attribute_ids):
        self._servers = servers
        if attribute_ids is None:
            self._attributes = None
        else:
            self._attributes = [
                Attribute.objects.get(pk=a) for a in attribute_ids
            ]
        self._server_attributes = dict()
        servers_by_type = defaultdict(list)
        for server in self._servers:
            self._server_attributes[server.pk] = {
                Attribute.specials['hostname']: server.hostname,
                Attribute.specials['intern_ip']: server.intern_ip,
                Attribute.specials['servertype']: server.servertype,
                Attribute.specials['project']: server.project,
            }
            servers_by_type[server.servertype].append(server)

        self._select_attributes(servers_by_type.keys())
        self._initialize_attributes(servers_by_type)
        self._add_attributes(servers_by_type)
        self._add_related_attributes(servers_by_type)

    def _select_attributes(self, servertypes):
        self._attributes_by_type = defaultdict(set)
        self._servertypes_by_attribute = defaultdict(list)
        self._related_servertype_attributes = []
        for sa in ServertypeAttribute.query(servertypes, self._attributes):
            self._select_servertype_attribute(sa)

    def _select_servertype_attribute(self, sa):
        self._attributes_by_type[sa.attribute.type].add(sa.attribute)
        self._servertypes_by_attribute[sa.attribute].append(sa.servertype)

        related_via_attribute = sa.related_via_attribute
        if related_via_attribute:
            # TODO: Order the list in a way to support recursive related
            # attributes.
            self._related_servertype_attributes.append(sa)

            # If we have related attributes in the attribute list, we have
            # to add the relations in there, too.  We are going to use
            # those to query the related attributes.
            if self._attributes is not None:
                self._select_servertype_attribute(ServertypeAttribute.query(
                    (sa.servertype, ), (related_via_attribute, )
                ).get())

    def _initialize_attributes(self, servers_by_type):
        for attribute, servertypes in self._servertypes_by_attribute.items():
            init = attribute.initializer()
            for servertype in servertypes:
                for server in servers_by_type[servertype]:
                    self._server_attributes[server.pk][attribute] = init()

    def _add_attributes(self, servers_by_type):
        """Add the attributes to the results"""
        for key, attributes in self._attributes_by_type.items():
            if key == 'supernet':
                for attribute in attributes:
                    self._add_supernet_attribute(attribute, (
                        s for st in self._servertypes_by_attribute[attribute]
                        for s in servers_by_type[st]
                    ))
            elif key == 'reverse_hostname':
                reversed_attributes = {
                    a.reversed_attribute: a for a in attributes
                }
                for sa in ServerHostnameAttribute.objects.filter(
                    value_id__in=self._server_attributes.keys(),
                    _attribute__in=reversed_attributes.keys(),
                ).select_related('server'):
                    self._add_attribute_value(
                        sa.value_id,
                        reversed_attributes[sa.attribute],
                        sa.server.hostname
                    )
            else:
                for sa in ServerAttribute.get_model(key).objects.filter(
                    server_id__in=self._server_attributes.keys(),
                    _attribute__in=attributes,
                ):
                    self._add_attribute_value(
                        sa.server_id, sa.attribute, sa.get_value()
                    )

    def _add_related_attributes(self, servers_by_type):
        for servertype_attribute in self._related_servertype_attributes:
            self._add_related_attribute(servertype_attribute, servers_by_type)

    def _add_supernet_attribute(self, attribute, servers):
        """Merge-join networks to the servers

        This function takes advantage of networks in the same servertype not
        overlapping with each other.
        """
        target = None
        for source in sorted(servers, key=lambda s: sort_key(s.intern_ip)):
            # Check the previous target
            if target is not None:
                network = target.intern_ip.network
                if network.version != source.intern_ip.version:
                    target = None
                elif network.broadcast_address < source.intern_ip.ip:
                    target = None
                elif source.intern_ip not in network:
                    continue
            # Check for a new target
            if target is None:
                try:
                    target = source.get_supernet(attribute.target_servertype)
                except Server.DoesNotExist:
                    continue
            self._server_attributes[source.pk][attribute] = target

    def _add_related_attribute(self, servertype_attribute, servers_by_type):
        attribute = servertype_attribute.attribute
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related = defaultdict(list)
        for target in servers_by_type[servertype_attribute.servertype]:
            attributes = self._server_attributes[target.pk]
            if related_via_attribute in attributes:
                if related_via_attribute.multi:
                    for source in attributes[related_via_attribute]:
                        servers_by_related[source].append(target)
                else:
                    source = attributes[related_via_attribute]
                    servers_by_related[source].append(target)

        # Then, query and set the related attributes
        for sa in ServerAttribute.get_model(attribute.type).objects.filter(
            server__hostname__in=servers_by_related.keys(),
            _attribute=attribute,
        ).select_related('server'):
            for target in servers_by_related[sa.server]:
                self._add_attribute_value(
                    target.pk, sa.attribute, sa.get_value()
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

    def get_order_by_attribute(self, server_id, attribute):
        """Return a tuple to sort items by the key

        We want the servers which doesn't have the attribute at all
        to appear at last, the server which the attribute is not set
        to appear in the beginning, and the rest in between.  Keep in
        mind that some datatypes are not sortable with each other, some
        not even with None, so we have to so something in here.
        """
        if attribute not in self._server_attributes[server_id]:
            return 1, None
        value = self._server_attributes[server_id][attribute]
        if value is None:
            return -1, None
        if attribute.multi:
            return 0, tuple(sort_key(v) for v in value)
        return 0, sort_key(value)

    def get_attributes(self, server_id, join_results):  # NOQA: C901
        yield 'object_id', server_id
        server_attributes = self._server_attributes[server_id]
        for attribute, value in server_attributes.items():
            if self._attributes is None or attribute in self._attributes:
                if attribute.pk in ('project', 'servertype'):
                    yield attribute.pk, value.pk
                elif attribute.type == 'inet':
                    if value is None:
                        yield attribute.pk, None
                    else:
                        servertype_attribute = Attribute.specials['servertype']
                        servertype = server_attributes[servertype_attribute]
                        if servertype.ip_addr_type in ('host', 'loadbalancer'):
                            yield attribute.pk, value.ip
                        else:
                            assert servertype.ip_addr_type == 'network'
                            yield attribute.pk, value.network
                elif attribute.pk in join_results:
                    if attribute.multi:
                        yield attribute.pk, {
                            join_results[attribute.pk][v.server_id]
                            for v in value
                        }
                    else:
                        yield attribute.pk, join_results[attribute.pk][
                            value.server_id
                        ]
                elif attribute.multi:
                    yield attribute.pk, {
                        v.hostname if isinstance(v, Server) else v
                        for v in value
                    }
                elif isinstance(value, Server):
                    yield attribute.pk, value.hostname
                else:
                    yield attribute.pk, value

    def get_servers_to_join(self, attribute_id):
        # The join attribute must be in our list.
        for attribute in self._attributes:
            if attribute.pk == attribute_id:
                break

        servers = set()
        for server_attributes in self._server_attributes.values():
            if attribute in server_attributes:
                if attribute.multi:
                    for server in server_attributes[attribute]:
                        servers.add(server)
                else:
                    servers.add(server_attributes[attribute])
        return servers


def sort_key(value):
    if isinstance(value, (IPv4Address, IPv6Address)):
        return value.version, value
    if isinstance(value, (Servertype, Project)):
        return value.pk
    return value
