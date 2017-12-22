from collections import defaultdict
from ipaddress import IPv4Address, IPv6Address

from django.core.exceptions import ValidationError

from adminapi.dataset import BaseQuery, BaseServerObject
from adminapi.filters import BaseFilter
from serveradmin.serverdb.models import (
    Project,
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server,
    ServerAttribute,
    ServerHostnameAttribute,
)
from serveradmin.serverdb.query_filterer import QueryFilterer
from serveradmin.dataset.commit import commit_changes


class Query(BaseQuery):
    def __init__(self, filters, restrict=None, order_by=None):
        self._filters = {}
        for attribute_id, filter_obj in filters.items():
            try:
                attribute = Attribute.objects.get(pk=attribute_id)
            except Attribute.DoesNotExist:
                raise ValidationError(
                    'Invalid attribute: {0}'.format(attribute_id)
                )
            if isinstance(filter_obj, BaseFilter):
                self._filters[attribute] = filter_obj
            else:
                self._filters[attribute] = BaseFilter(filter_obj)
        if restrict:
            self._restrict = {Attribute.objects.get(pk=a) for a in restrict}
        else:
            self._restrict = None
        if order_by:
            self._order_by = [Attribute.objects.get(pk=a) for a in order_by]
        else:
            self._order_by = None
        self._results = None
        self._num_dirty = 0

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    # XXX: Deprecated
    def restrict(self, *attrs):
        for attribute_id in attrs:
            try:
                self._restrict.add(Attribute.objects.get(pk=attribute_id))
            except Attribute.DoesNotExist:
                raise ValidationError(
                    'Invalid attribute: {0}'.format(attribute_id)
                )
        return self

    # XXX: Deprecated
    def order_by(self, *attribute_ids):
        self._order_by = []
        for attribute_id in attribute_ids:
            try:
                self._order_by.append(Attribute.objects.get(pk=attribute_id))
            except Attribute.DoesNotExist:
                raise ValidationError(
                    'Invalid attribute: {0}'.format(attribute_id)
                )
        return self

    def _get_query_filterer(self):
        attributes = []
        filters = {}
        servertypes = set(Servertype.objects.all())
        for attribute, filt in self._filters.items():

            # We can just deal with the servertype filters ourself.
            if attribute.pk == 'servertype':
                servertypes = {s for s in servertypes if filt.matches(s.pk)}
            else:
                filters[attribute] = filt

            if not attribute.special:
                attributes.append(attribute)

        if attributes:
            attribute_servertypes = defaultdict(set)
            for sa in ServertypeAttribute.query(attributes=attributes).all():
                attribute_servertypes[sa.attribute].add(sa.servertype)
            for new in attribute_servertypes.values():
                servertypes = servertypes.intersection(new)

        if not servertypes:
            return None

        return QueryFilterer(servertypes, filters)

    def get_results(self):
        if self._results is None:
            self._fetch_results()
        return self._results

    def _fetch_results(self):
        filterer = self._get_query_filterer()
        if filterer is None:
            self._results = []
            return

        self._server_attributes = dict()
        servers_by_type = defaultdict(list)
        servers = tuple(Server.objects.raw(filterer.build_sql()))
        for server in servers:
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

        server_ids = self._server_attributes.keys()
        if self._order_by:
            server_ids = sorted(server_ids, key=self._order_by_key)
        self._results = [
            ServerObject(self._get_attributes(i), i, self) for i in server_ids
        ]

    def _select_attributes(self, servertypes):
        self._attributes_by_type = defaultdict(set)
        self._servertypes_by_attribute = defaultdict(list)
        self._related_servertype_attributes = []
        if self._restrict and self._order_by:
            attributes = list(self._restrict) + self._order_by
        else:
            attributes = self._restrict
        for sa in ServertypeAttribute.query(servertypes, attributes).all():
            self._select_servertype_attribute(sa)

    def _select_servertype_attribute(self, sa):
        self._attributes_by_type[sa.attribute.type].add(sa.attribute)
        self._servertypes_by_attribute[sa.attribute].append(sa.servertype)

        related_via_attribute = sa.related_via_attribute
        if related_via_attribute:
            # TODO: Order the list in a way to support recursive related
            # attributes.
            self._related_servertype_attributes.append(sa)

            # If we have related attributes in the restrict list, we have
            # to add the relations in there, too.  We are going to use
            # those to query the related attributes.
            if self._restrict:
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
            self._server_attributes[source.pk][attribute] = target.hostname

    def _add_related_attribute(self, servertype_attribute, servers_by_type):
        attribute = servertype_attribute.attribute
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related_hostnames = defaultdict(list)
        for server in servers_by_type[servertype_attribute.servertype]:
            attributes = self._server_attributes[server.pk]
            if related_via_attribute in attributes:
                if related_via_attribute.multi:
                    for hostname in attributes[related_via_attribute]:
                        servers_by_related_hostnames[hostname].append(server)
                else:
                    hostname = attributes[related_via_attribute]
                    servers_by_related_hostnames[hostname].append(server)

        # Then, query and set the related attributes
        for sa in ServerAttribute.get_model(attribute.type).objects.filter(
            server__hostname__in=servers_by_related_hostnames.keys(),
            _attribute=attribute,
        ).select_related('server'):
            for server in servers_by_related_hostnames[sa.server.hostname]:
                self._add_attribute_value(
                    server.pk, sa.attribute, sa.get_value()
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

    def _order_by_key(self, key):
        return tuple(self._order_by_attribute(key, a) for a in self._order_by)

    def _order_by_attribute(self, key, attribute):
        """Return a tuple to sort items by the key

        We want the servers which doesn't have the attribute at all
        to appear at last, the server which the attribute is not set
        to appear in the beginning, and the rest in between.  Keep in
        mind that some datatypes are not sortable with each other, some
        not even with None, so we have to so something in here.
        """
        if attribute not in self._server_attributes[key]:
            return 1, None
        value = self._server_attributes[key][attribute]
        if value is None:
            return -1, None
        if attribute.multi:
            return 0, tuple(sort_key(v) for v in value)
        return 0, sort_key(value)

    def _get_attributes(self, server_id):
        yield 'object_id', server_id
        server_attributes = self._server_attributes[server_id]
        for attribute, value in server_attributes.items():
            if not self._restrict or attribute in self._restrict:
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
                else:
                    yield attribute.pk, value


class ServerObject(BaseServerObject):
    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        commit_changes(commit, app=app, user=user)
        self._confirm_changes()

    @classmethod
    def new(cls, servertype, project, hostname, intern_ip):
        attribute_values = [
            ('servertype', servertype.pk),
            ('project', project.pk),
            ('hostname', hostname),
            ('intern_ip', intern_ip),
        ]
        for sa in servertype.attributes.all():
            attribute_values.append((sa.attribute.pk, sa.get_default_value()))
        return cls(attribute_values)


def sort_key(value):
    if isinstance(value, (IPv4Address, IPv6Address)):
        return value.version, value
    if isinstance(value, (Servertype, Project)):
        return value.pk
    return value


# XXX: Deprecated
def query(**kwargs):
    return Query(kwargs)
