# XXX: This module is pretty complicated even though the functions are not
# on their own.  They store a lot of stuff on the object.  It is probably
# a good idea to refactor this by using more top level functions instead of
# object methods.

from collections import defaultdict
from ipaddress import IPv4Address, IPv6Address

from django.core.exceptions import ValidationError

from adminapi.dataset import DatasetObject
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
    def __init__(self, servers, restrict, order_by=None):
        self._servers = list(servers)
        self._order_by = order_by

        if restrict is None:
            self._attributes = None
        else:
            self._attributes = {}

            for item in restrict:
                if isinstance(item, dict):
                    if len(item) != 1:
                        raise ValidationError('Malformatted join restriction')
                    for attribute_id, value in item.items():
                        pass
                else:
                    attribute_id = item
                    value = None

                attribute = Attribute.objects.get(pk=attribute_id)
                self._attributes[attribute] = value

        self._server_attributes = {}
        servers_by_type = defaultdict(list)
        for server in self._servers:
            self._server_attributes[server] = {
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

    def __iter__(self):
        servers = self._servers
        if self._order_by:
            def order_by_key(key):
                return tuple(
                    self._get_order_by_attribute(key, a)
                    for a in self._order_by
                )

            servers = sorted(servers, key=order_by_key)

        return (DatasetObject(self._get_attributes(s)) for s in servers)

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
                    self._server_attributes[server][attribute] = init()

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
                    server__in=self._server_attributes.keys(),
                    _attribute__in=attributes,
                ):
                    self._add_attribute_value(
                        sa.server, sa.attribute, sa.get_value()
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
        for source in sorted(servers, key=lambda s: _sort_key(s.intern_ip)):
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
            self._server_attributes[source][attribute] = target

    def _add_related_attribute(self, servertype_attribute, servers_by_type):
        attribute = servertype_attribute.attribute
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related = defaultdict(list)
        for target in servers_by_type[servertype_attribute.servertype]:
            attributes = self._server_attributes[target]
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
                self._add_attribute_value(target, sa.attribute, sa.get_value())

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

    def _get_attributes(self, server):   # NOQA: C901
        yield 'object_id', server.pk
        server_attributes = self._server_attributes[server]
        join_results = self._get_join_results()
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
                elif value is None:
                    yield attribute.pk, None
                elif attribute in join_results:
                    if attribute.multi:
                        yield attribute.pk, [
                            join_results[attribute][v] for v in value
                        ]
                    else:
                        yield attribute.pk, join_results[attribute][value]
                elif attribute.multi:
                    yield attribute.pk, {
                        v.hostname if isinstance(v, Server) else v
                        for v in value
                    }
                elif isinstance(value, Server):
                    yield attribute.pk, value.hostname
                else:
                    yield attribute.pk, value

    def _get_join_results(self):
        results = dict()
        if self._attributes:
            for attribute, restrict in self._attributes.items():
                if restrict is not None:
                    servers = self._get_servers_to_join(attribute)
                    server_objs = type(self)(servers, restrict)
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
    if isinstance(value, (Servertype, Project)):
        return value.pk
    return value


def get_default_attribute_values(servertype_id):
    servertype = Servertype.objects.get(pk=servertype_id)
    attribute_values = {}

    for attribute_id in Attribute.specials:
        if attribute_id == 'servertype':
            value = servertype_id
        elif attribute_id == 'project' and servertype.fixed_project:
            value = servertype.fixed_project.pk
        else:
            value = None
        attribute_values[attribute_id] = value

    for sa in servertype.attributes.all():
        attribute_values[sa.attribute.pk] = sa.get_default_value()

    return attribute_values
