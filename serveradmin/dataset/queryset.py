from datetime import datetime
from collections import OrderedDict

from django.db import connection

from adminapi.dataset.base import BaseQuerySet, BaseServerObject
from adminapi.utils import IP, IPv6
from serveradmin.dataset.base import lookups, ServerTableSpecial
from serveradmin.dataset.validation import check_attributes
from serveradmin.dataset import filters
from serveradmin.dataset.commit import commit_changes
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
            limit,
            offset,
        ):

        for attr_name, filt in filters.iteritems():
            filt.typecast(attr_name)

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
            args.append(u'{0}={1}'.format(attr_name, value.as_code()))

        if hide_extra:
            # FIXME: Add restrict/limit/augment etc.
            extra = u''

        return u'query({0}){1}'.format(u', '.join(args), extra)

class QuerySet(BaseQuerySet):
    def __init__(self, filters):
        check_attributes(filters.keys())
        super(QuerySet, self).__init__(filters)
        self.attributes = lookups.attr_names
        self._order_by = None
        self._order_dir = 'asc'
        self._limit = None
        self._offset = None

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    def get_raw_results(self):
        self._get_results()
        return self._results

    def get_num_rows(self):
        builder = self._get_query_builder_with_filters()
        builder.sql_keywords.append('count(*)')

        with connection.cursor() as cursor:
            cursor.execute(builder.build_sql())
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

        self._order_by = order_by
        self._order_dir = order_dir

        return self

    def _get_results(self):
        if self._results is None:
            self._results = self._fetch_results()

    def _get_query_builder_with_filters(self):

        # XXX: Dirty hack for the old database structure
        builder = QueryBuilder()
        optional_filters = (filters.OptionalFilter, filters.Not)
        for attr, f in self._filters.iteritems():
            attr_obj = lookups.attr_names[attr]
            optional = (
                        isinstance(f, optional_filters)
                    or
                        attr_obj.type == 'boolean'
                )
            builder.add_attribute(attr, optional)
            builder.add_filter(attr, f)

        return builder

    def _fetch_results(self):
        builder = self._get_query_builder_with_filters()

        # Copy order_by from instance to local variable to allow LIMIT
        # to set it in the query (but not in the instance) if it is
        # not set
        if self._order_by:
            order_by = self._order_by
            order_dir = self._order_dir
            builder.add_attribute(order_by, optional=True)
            builder.add_ordering((order_by, order_dir))
        else:
            order_by = u'hostname'
            order_dir = u'asc'

        if self._limit:
            builder.add_limit(self._limit)

        if self._offset:
            builder.add_offset(self._offset)

        for attr in (
                'object_id',
                'hostname',
                'intern_ip',
                'segment',
                'servertype',
                'project',
            ):
            builder.add_attribute(attr)
            builder.add_select(attr)
        builder.sql_keywords.append('DISTINCT')
        sql_stmt = builder.build_sql()

        # We need to preserve ordering if ordering is requested, otherwise
        # we can use normal dict as it performs better.
        if order_by:
            server_data = OrderedDict()
        else:
            server_data = dict()

        servertype_lookup = dict(
                (k, v.name) for k, v in lookups.stype_ids.iteritems()
            )
        restrict = self._restrict

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
                        u'intern_ip': IP(intern_ip),
                        u'segment': segment,
                        u'servertype': servertype_lookup[stype],
                        u'project': project,
                    }
                else:
                    attrs = {}
                    if u'hostname' in restrict:
                        attrs[u'hostname'] = hostname
                    if u'intern_ip' in restrict:
                        attrs[u'intern_ip'] = IP(intern_ip)
                    if u'segment' in restrict:
                        attrs[u'segment'] = segment
                    if u'servertype' in restrict:
                        attrs[u'servertype'] = servertype_lookup[stype]
                    if u'project' in restrict:
                        attrs[u'project'] = project

                server_object = ServerObject(attrs, server_id, self)
                server_data[server_id] = server_object

                for attr in lookups.stype_ids[stype].attributes:
                    if attr.multi:
                        if not restrict or attr.name in restrict:
                            dict.__setitem__(server_object, attr.name, set())

        # Return early if there are no servers (= empty dict)
        if not server_data:
            return server_data

        # Remove attributes from adm_server from the restrict set
        add_attributes = True
        if restrict:
            for attr_obj in lookups.attr_names.itervalues():
                if isinstance(attr_obj.special, ServerTableSpecial):
                    restrict.discard(attr_obj.name)
            # if restrict is empty now, there are no attributes to fetch
            # from the attrib_values table, but just attributes from
            # admin_server table. We can return early
            if not restrict:
                add_attributes = False

        if add_attributes:
            self._add_additional_attrs(server_data, restrict)

        return server_data

    def _add_additional_attrs(self, server_data, restrict):

        server_ids = u', '.join(map(str, server_data.iterkeys()))
        sql_stmt = (
                u'SELECT server_id, attrib_id, value '
                u'FROM attrib_values '
                u'WHERE server_id IN ({0})'
            ).format(server_ids)

        if restrict:
            restrict_ids = u', '.join(
                    str(lookups.attr_names[attr_name].pk)
                    for attr_name in restrict
                )
            sql_stmt += u' AND attrib_id IN ({0})'.format(restrict_ids)

        _getitem = dict.__getitem__
        _setitem = dict.__setitem__

        with connection.cursor() as cursor:
            cursor.execute(sql_stmt)
            attr_ids = lookups.attr_ids
            for server_id, attr_id, value in cursor.fetchall():
                # Typecasting is inlined here for performance reasons
                attr = attr_ids[attr_id]
                attr_type = attr.type
                if attr_type == u'integer':
                    value = int(value)
                elif attr_type == u'boolean':
                    value = value == '1'
                elif attr_type == u'ip':
                    value = IP(value)
                elif attr_type == u'ipv6':
                    value = IPv6.from_hex(value)
                elif attr_type == u'datetime':
                    value = datetime.fromtimestamp(int(value))

                # Using dict-methods to bypass ServerObject's special properties
                if attr.multi:
                    # Bypass MultiAttr wrapping in ServerObject.__getitem__
                    _getitem(server_data[server_id], attr.name).add(value)
                else:
                    _setitem(server_data[server_id], attr.name, value)

class ServerObject(BaseServerObject):
    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        commit_changes(commit, app=app, user=user)
        self._confirm_changes()

    def __reduce__(self):
        # Just pickle it as normal dict
        tpl = dict.__reduce__(self)
        instance_dict = tpl[2].copy()
        del instance_dict[u'_queryset']
        return (tpl[0], tpl[1], instance_dict)
