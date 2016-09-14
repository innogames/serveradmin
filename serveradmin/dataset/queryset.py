from collections import defaultdict, OrderedDict
from ipaddress import ip_address, ip_network

from django.db import connection
from django.core.exceptions import ValidationError

from adminapi.dataset.base import BaseQuerySet, BaseServerObject

from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    ServerAttribute,
    ServerHostnameAttribute,
)
from serveradmin.dataset.commit import commit_changes
from serveradmin.dataset.filters import Any
from serveradmin.dataset.querybuilder import QueryBuilder

CACHE_MIN_QS_COUNT = 3
NUM_OBJECTS_FOR_FILECACHE = 50


class QuerySetRepresentation(object):
    """Object that can be easily pickled without storing to much data.
    """

    def __init__(
        self,
        filters,
        restrict,
        augmentations,
        order_by,
        order_dir,
    ):
        self.filters = filters
        self.restrict = restrict
        self.augmentations = augmentations
        self.order_by = order_by
        self.order_dir = order_dir

    def __hash__(self):
        h = 0
        if self.restrict:
            for val in self.restrict:
                h ^= hash(val)
        if self.augmentations:
            for val in self.augmentations:
                h ^= hash(val)
        for attr_name, attr_filter in self.filters.iteritems():
            h ^= hash(attr_name)
            h ^= hash(attr_filter)

        if self.order_by:
            h ^= hash(self.order_by)
            h ^= hash(self.order_dir)

        return h

    def __eq__(self, other):
        if not isinstance(other, QuerySetRepresentation):
            return False

        if self.restrict and other.restrict:
            if set(self.restrict) - set(other.restrict):
                return False
        elif self.restrict or other.restrict:
            return False

        if self.augmentations and other.augmentations:
            if set(self.augmentations) - set(other.augmentations):
                return False
        elif self.augmentations or other.augmentations:
            return False

        if len(self.filters) != len(other.filters):
            return False

        for key in self.filters:
            if key not in other.filters:
                return False
            if self.filters[key] != other.filters[key]:
                return False

        if self.order_by != other.order_by:
            return False

        if self.order_dir != other.order_dir:
            return False

        return True

    def as_code(self):
        args = []
        for attr_name, value in self.filters.iteritems():
            args.append('{0}={1}'.format(attr_name, value.as_code()))
        return 'query({0})'.format(', '.join(args))


class QuerySet(BaseQuerySet):
    def __init__(self, filters):
        self.attributes = {a.pk: a for a in Attribute.objects.all()}
        for attribute_id in filters.keys():
            if attribute_id not in self.attributes:
                raise ValidationError(
                    'Invalid attribute: {0}'.format(attribute_id)
                )
        for attribute_name, filter_obj in filters.items():
            filter_obj.typecast(self.attributes[attribute_name])
        super(QuerySet, self).__init__(filters)
        self._order_by = None
        self._order_dir = 'asc'

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    def get_representation(self):
        return QuerySetRepresentation(
            self._filters,
            self._restrict,
            self._augmentations,
            self._order_by,
            self._order_dir,
        )

    def restrict(self, *attrs):
        for attribute_id in attrs:
            if attribute_id not in self.attributes:
                raise ValidationError(
                    'Invalid attribute: {0}'.format(attribute_id)
                )
        return super(QuerySet, self).restrict(*attrs)

    def order_by(self, order_by, order_dir='asc'):
        if order_by not in self.attributes:
            raise ValidationError(
                'Invalid attribute: {0}'.format(order_by)
            )
        if order_dir not in ('asc', 'desc'):
            raise ValueError('Invalid order direction')

        self._order_by = self.attributes[order_by]
        self._order_dir = order_dir

        # We need the attribute to order by.
        if self._restrict:
            self._restrict.add(order_by)

        return self

    def _get_query_builder_with_filters(self):
        real_attributes = []
        builder = QueryBuilder()
        for attr, filt in self._filters.iteritems():
            attribute = self.attributes[attr]
            builder.add_filter(attribute, filt)
            if not attribute.special:
                real_attributes.append(attribute)

        if real_attributes:
            attribute_servertype_ids = defaultdict(set)
            for sa in ServertypeAttribute.get_by_attributes(real_attributes):
                attribute_servertype_ids[sa.attribute].add(sa.servertype.pk)
            sets = attribute_servertype_ids.values()
            intersect = reduce(set.intersection, sets[1:], sets[0])
            builder.add_filter(self.attributes['servertype'], Any(*intersect))

        return builder

    def _fetch_results(self):
        builder = self._get_query_builder_with_filters()

        # We can only push-down the order-by to the database, if
        # it is one of the special attributes.  The query-builder
        # is not capable of doing order by for real attributes.
        # Otherwise we have to do ordering ourself, later.
        if not self._order_by or self._order_by.special:
            if self._order_by:
                builder.add_order_by(self._order_by, self._order_dir)

            # In this case we need to preserve ordering, otherwise
            # we can use normal dict as it performs better.
            self._results = OrderedDict()
        else:
            self._results = dict()

        restrict = self._restrict
        servers_by_type = defaultdict(list)

        with connection.cursor() as cursor:
            cursor.execute(builder.build_sql())

            for (
                server_id,
                hostname,
                intern_ip,
                segment_id,
                servertype_id,
                project_id,
            ) in cursor.fetchall():
                servertype = Servertype.objects.get(pk=servertype_id)

                attrs = {}
                if not restrict or 'hostname' in restrict:
                    attrs['hostname'] = hostname
                if not restrict or 'intern_ip' in restrict:
                    if servertype.ip_addr_type == 'null':
                        attrs['intern_ip'] = None
                    elif servertype.ip_addr_type in ('host', 'loadbalancer'):
                        attrs['intern_ip'] = ip_address(intern_ip)
                    else:
                        assert servertype.ip_addr_type == 'network'
                        attrs['intern_ip'] = ip_network(intern_ip)
                if not restrict or 'segment' in restrict:
                    attrs['segment'] = segment_id
                if not restrict or 'servertype' in restrict:
                    attrs['servertype'] = servertype_id
                if not restrict or 'project' in restrict:
                    attrs['project'] = project_id

                server_object = ServerObject(attrs, server_id, self)
                self._results[server_id] = server_object
                servers_by_type[servertype].append(server_object)

        self._select_attributes(servers_by_type)
        self._add_attributes(servers_by_type)
        if self._order_by and not self._order_by.special:
            self._sort()

    def _select_attributes(self, servers_by_type):
        self._attributes_by_type = defaultdict(list)
        self._servertypes_by_attribute = defaultdict(list)
        self._related_servertype_attributes = []

        # First, prepare the dictionary for lookups by attribute
        servertype_attributes = defaultdict(list)
        for servertype in servers_by_type.keys():
            for sa in servertype.attributes.all():
                servertype_attributes[sa.attribute].append(sa)
        # Then, process the attributes
        for attribute in servertype_attributes.keys():
            if not self._restrict or attribute.pk in self._restrict:
                self._select_attribute(servertype_attributes, attribute)

    def _select_attribute(self, servertype_attributes, attribute):
        self._attributes_by_type[attribute.type].append(attribute)

        for sa in servertype_attributes[attribute]:
            self._servertypes_by_attribute[attribute].append(sa.servertype)

            if sa.related_via_attribute:
                # TODO Order the list in a way to support recursive related
                # attributes.
                self._related_servertype_attributes.append(sa)

                # If we have related attributes in the restrict list, we have
                # to add the relations in there, too.  We are going to use
                # those to query the related attributes.
                if self._restrict:
                    new = sa.related_via_attribute

                    if new not in self._attributes_by_type[new.type]:
                        self._select_attribute(servertype_attributes, new)

    def _add_attributes(self, servers_by_type):
        """Add the attributes to the results"""

        # Step 0: Initialize the multi attributes
        for attribute, servertypes in self._servertypes_by_attribute.items():
            if attribute.multi:
                for servertype in servertypes:
                    for server in servers_by_type[servertype]:
                        dict.__setitem__(server, attribute.pk, set())

        # Step 1: Query the materialized attributes by their types
        for key, attributes in self._attributes_by_type.items():
            model = ServerAttribute.get_model(key)
            if model:
                for sa in model.objects.filter(
                    server_id__in=self._results.keys(),
                    _attribute__in=attributes,
                ):
                    self._add_attribute_value(
                        self._results[sa.server_id],
                        sa.attribute,
                        sa.get_value(),
                    )

        # Step 2: Add the containing networks
        for attribute in self._attributes_by_type['supernet']:
            # TODO Refactor this using Django ORM
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT server.server_id,'
                    '       supernet.hostname'
                    '   FROM server'
                    '       JOIN server AS supernet'
                    '           ON server.intern_ip <<= supernet.intern_ip'
                    '   WHERE server.server_id IN ({0})'
                    "       AND supernet.servertype_id = '{1}'"
                    .format(
                        ', '.join(
                            str(o.object_id)
                            for s in self._servertypes_by_attribute[attribute]
                            for o in servers_by_type[s]
                        ),
                        attribute.target_servertype.pk,
                    )
                )
                for server_id, value in cursor.fetchall():
                    self._add_attribute_value(
                        self._results[server_id],
                        attribute,
                        value,
                    )

        # Step 3: Add the reverse attributes
        for attribute in self._attributes_by_type['reverse_hostname']:
            for sa in ServerHostnameAttribute.objects.filter(
                value_id__in=self._results.keys(),
                _attribute_id=attribute.reversed_attribute.pk,
            ):
                self._add_attribute_value(
                    self._results[sa.value_id],
                    attribute,
                    sa.get_reverse_value(),
                )

        # Step 4: Add the related attributes
        for servertype_attribute in self._related_servertype_attributes:
            self._add_related_attribute(servertype_attribute, servers_by_type)

    def _add_related_attribute(self, servertype_attribute, servers_by_type):
        attribute = servertype_attribute.attribute
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related_hostnames = defaultdict(list)
        for server in servers_by_type[servertype_attribute.servertype]:
            if related_via_attribute.pk in server:
                if related_via_attribute.multi:
                    for hostname in server[related_via_attribute.pk]:
                        servers_by_related_hostnames[hostname].append(server)
                else:
                    hostname = server[related_via_attribute.pk]
                    servers_by_related_hostnames[hostname].append(server)

        # Then, query and set the related attributes
        for sa in ServerAttribute.get_model(attribute.type).objects.filter(
            server__hostname__in=servers_by_related_hostnames.keys(),
            _attribute=attribute,
        ).select_related('server'):
            for server in servers_by_related_hostnames[sa.server.hostname]:
                self._add_attribute_value(server, sa.attribute, sa.get_value())

    def _add_attribute_value(self, server, attribute, value):
        if attribute.multi:
            dict.__getitem__(server, attribute.pk).add(value)
        else:
            dict.__setitem__(server, attribute.pk, value)

    def _sort(self):
        self._results = OrderedDict(sorted(
            self._results.items(),
            key=lambda x: (
                self._order_by.pk in x[1], x[1].get(self._order_by.pk)
            ),
            reverse=(self._order_dir == 'desc'),
        ))


class ServerObject(BaseServerObject):
    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        commit_changes(commit, app=app, user=user)
        self._confirm_changes()

    def __reduce__(self):
        # Just pickle it as normal dict
        tpl = dict.__reduce__(self)
        instance_dict = tpl[2].copy()
        del instance_dict['_queryset']
        return (tpl[0], tpl[1], instance_dict)
