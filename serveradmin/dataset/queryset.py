from collections import defaultdict, OrderedDict
from ipaddress import ip_address

from django.db import connection

from adminapi.dataset.base import BaseQuerySet, BaseServerObject

from serveradmin.serverdb.models import (
    ServertypeAttribute,
    ServerAttribute,
)
from serveradmin.dataset.base import lookups
from serveradmin.dataset.commit import commit_changes
from serveradmin.dataset.querybuilder import QueryBuilder
from serveradmin.dataset.validation import check_attributes

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
        limit,
        offset,
    ):
        self.filters = filters
        self.restrict = restrict
        self.augmentations = augmentations
        self.order_by = order_by
        self.order_dir = order_dir
        self.limit = limit
        self.offset = offset

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

        if self.limit:
            h ^= hash(self.limit)

        if self.offset:
            h ^= hash(self.offset)

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

        if self.limit != other.limit:
            return False

        if self.offset != other.offset:
            return False

        return True

    def as_code(self, hide_extra=True):
        args = []
        for attr_name, value in self.filters.iteritems():
            args.append('{0}={1}'.format(attr_name, value.as_code()))

        if hide_extra:
            # FIXME: Add restrict/limit/augment etc.
            extra = ''

        return 'query({0}){1}'.format(', '.join(args), extra)


class QuerySet(BaseQuerySet):
    def __init__(self, filters):
        check_attributes(filters.keys())
        for attribute_name, filter_obj in filters.items():
            filter_obj.typecast(lookups.attributes[attribute_name])
        super(QuerySet, self).__init__(filters)
        self.attributes = lookups.attributes
        self._order_by = None
        self._order_dir = 'asc'
        self._limit = None
        self._offset = None

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    def get_num_rows(self):
        builder = self._get_query_builder_with_filters()

        with connection.cursor() as cursor:
            cursor.execute(builder.build_sql(count=True))
            return cursor.fetchone()[0]

    def get_representation(self):
        return QuerySetRepresentation(
                self._filters,
                self._restrict,
                self._augmentations,
                self._order_by,
                self._order_dir,
                self._limit,
                self._offset,
            )

    def restrict(self, *attrs):
        check_attributes(attrs)
        return super(QuerySet, self).restrict(*attrs)

    def limit(self, value):
        if value < 1:
            raise ValueError('Invalid limit')

        self._limit = value
        return self

    def offset(self, value):
        if value < 1:
            raise ValueError('Invalid offset')

        self._offset = value
        return self

    def order_by(self, order_by, order_dir='asc'):
        check_attributes([order_by])
        if order_dir not in ('asc', 'desc'):
            raise ValueError('Invalid order direction')

        self._order_by = lookups.attributes[order_by]
        self._order_dir = order_dir

        return self

    def _get_query_builder_with_filters(self):
        builder = QueryBuilder()
        for attr, filt in self._filters.iteritems():
            builder.add_filter(lookups.attributes[attr], filt)

        return builder

    def _fetch_results(self):
        builder = self._get_query_builder_with_filters()

        # Copy order_by from instance to local variable to allow LIMIT
        # to set it in the query (but not in the instance) if it is
        # not set
        if self._order_by:
            builder.add_order_by(self._order_by, self._order_dir)
        if self._limit:
            builder.add_limit(self._limit)
        if self._offset:
            builder.add_offset(self._offset)

        sql_stmt = builder.build_sql()

        # We need to preserve ordering if ordering is requested, otherwise
        # we can use normal dict as it performs better.
        if self._order_by:
            self._results = OrderedDict()
        else:
            self._results = dict()

        restrict = self._restrict
        servers_by_type = defaultdict(list)

        with connection.cursor() as cursor:
            cursor.execute(sql_stmt)

            for (
                server_id,
                hostname,
                intern_ip,
                segment,
                stype,
                project,
            ) in cursor.fetchall():

                if not restrict:
                    attrs = {
                        u'hostname': hostname,
                        u'intern_ip': ip_address(intern_ip),
                        u'segment': segment,
                        u'servertype': stype,
                        u'project': project,
                    }
                else:
                    attrs = {}
                    if u'hostname' in restrict:
                        attrs[u'hostname'] = hostname
                    if u'intern_ip' in restrict:
                        attrs[u'intern_ip'] = ip_address(intern_ip)
                    if u'segment' in restrict:
                        attrs[u'segment'] = segment
                    if u'servertype' in restrict:
                        attrs[u'servertype'] = stype
                    if u'project' in restrict:
                        attrs[u'project'] = project

                server_object = ServerObject(attrs, server_id, self)
                self._results[server_id] = server_object
                servers_by_type[stype].append(server_object)

        # Initialise multi attributes
        for sa in ServertypeAttribute.objects.all():
            if (
                sa.servertype.pk in servers_by_type and
                sa.attribute.multi and (
                    not self._restrict or sa.attribute.pk in self._restrict
                )
            ):
                for server in servers_by_type[sa.servertype.pk]:
                    dict.__setitem__(server, sa.attribute.pk, set())

        # Return early if there are no servers (= empty dict)
        if not self._results:
            return

        self._select_attributes(servers_by_type)
        self._add_attributes(servers_by_type)

    def _select_attributes(self, servers_by_type):
        self._materalized_attributes_by_type = defaultdict(set)
        self._related_servertype_attributes = []

        for sa in ServertypeAttribute.objects.all():
            if (
                sa.servertype.pk in servers_by_type and (
                    not self._restrict or sa.attribute.pk in self._restrict
                )
            ):
                self._select_attribute(sa)

    def _select_attribute(self, servertype_attribute):
        attribute = servertype_attribute.attribute

        if not servertype_attribute.related_via_attribute:
            self._materalized_attributes_by_type[attribute.type].add(attribute)
        else:
            self._related_servertype_attributes.append(servertype_attribute)

            # If we have related attributes in the restrict list, we have
            # to add the relations in there, too.  We are going to use those
            # to query the related attributes.
            if self._restrict:
                self._select_attribute(
                    servertype_attribute.get_related_via_servertype_attribute()
                )

    def _add_attributes(self, servers_by_type):
        """Add the attributes to the results"""

        # Step 1: Query the materialized attributes by their types
        for key, attributes in self._materalized_attributes_by_type.items():
            for sa in ServerAttribute.get_model(key).objects.filter(
                server_id__in=self._results.keys(),
                _attribute__in=attributes,
            ):
                self._add_attribute_value(sa.server_id, sa)

        # Step 2: Add the related attributes
        #
        # TODO Order the list in a way to support recursive related
        # attributes.
        for servertype_attribute in self._related_servertype_attributes:
            self._add_related_attribute(servertype_attribute, servers_by_type)

    def _add_related_attribute(self, servertype_attribute, servers_by_type):
        attribute = servertype_attribute.attribute
        related_via_attribute = servertype_attribute.related_via_attribute

        # First, index the related servers for fast access later
        servers_by_related_hostnames = defaultdict(list)
        for server in servers_by_type[servertype_attribute.servertype.pk]:
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
                self._add_attribute_value(server.pk, sa)

    def _add_attribute_value(self, server_id, server_attribute):
        server = self._results[server_id]
        attribute = server_attribute.attribute
        value = server_attribute.get_value()

        if attribute.multi:
            dict.__getitem__(server, attribute.pk).add(value)
        else:
            dict.__setitem__(server, attribute.pk, value)


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
