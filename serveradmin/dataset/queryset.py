from django.db import connection

from adminapi.dataset.base import BaseQuerySet, BaseServerObject
from adminapi.utils import IP
from serveradmin.dataset.base import lookups, ServerTableSpecial, CombinedSpecial
from serveradmin.dataset.validation import check_attributes
from serveradmin.dataset import filters
from serveradmin.dataset.commit import commit_changes
from serveradmin.dataset.cache import QuerysetCacher
from serveradmin.dataset.querybuilder import QueryBuilder

CACHE_MIN_QS_COUNT = 3
NUM_OBJECTS_FOR_FILECACHE = 50

class QuerySetRepresentation(object):
    """ Object that can be easily pickled without storing to much data.
    The main use is to compare querysets for caching. 
    """
    def __init__(self, filters, restrict, augmentations, offset, limit,
                 order_by, order_dir):
        for attr_name, filt in filters.iteritems():
            filt.typecast(attr_name)
        self.filters = filters
        self.restrict = restrict
        self.augmentations = augmentations
        self.offset = offset
        self.limit = limit
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

        if self.limit:
            h ^=  hash(self.offset)
            h ^=  hash(self.limit)

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

        if self.offset != other.offset or self.limit != other.limit:
            return False

        if self.order_by != other.order_by or self.order_dir != other.order_dir:
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
    def __init__(self, filters, bypass_cache=False):
        check_attributes(filters.keys())
        super(QuerySet, self).__init__(filters)
        self.attributes = lookups.attr_names
        self._bypass_cache = bypass_cache
        self._already_through_cache = False
        self._limit = None
        self._offset = None
        self._order_by = None
        self._order_dir = 'asc'
        self._num_rows = 0

    def commit(self, skip_validation=False, force_changes=False):
        commit = self._build_commit_object()
        commit_changes(commit, skip_validation, force_changes)
        self._confirm_changes()

    def get_raw_results(self):
        self._get_results()
        return self._results

    def get_num_rows(self):
        self._get_results()
        return self._num_rows

    def get_representation(self):
        return QuerySetRepresentation(self._filters, self._restrict,
                self._augmentations, self._offset, self._limit,
                self._order_by, self._order_dir)

    def restrict(self, *attrs):
        check_attributes(attrs)
        return super(QuerySet, self).restrict(*attrs)

    def limit(self, offset, limit=None):
        if limit is None:
            limit, offset = offset, 0
        
        if limit < 1:
            raise ValueError('Invalid limit')
        if offset < 0:
            raise ValueError('Invalid offset')
        
        self._offset = offset
        self._limit = limit
        
        return self

    def order_by(self, order_by, order_dir='asc'):
        check_attributes([order_by])
        if order_dir not in ('asc', 'desc'):
            raise ValueError('Invalid order direction')
        
        self._order_by = order_by
        self._order_dir = order_dir
        
        return self
    
    def _get_results(self):
        if self._results is not None:
            return
        if self._bypass_cache:
            self._results = self._fetch_results()
        else:
            if self._already_through_cache:
                self._results = self._fetch_results()
            else:
                self._already_through_cache = True
                cacher = QuerysetCacher(self, u'qs',
                        pre_store=self._cache_pre_store,
                        post_load=self._cache_post_load)
                self._results = cacher.get_results()

    def _fetch_results(self):
        # XXX: Dirty hack for the old database structure
        builder = QueryBuilder()
        _Optional = filters.Optional
        for attr, f in self._filters.iteritems():
            attr_obj = lookups.attr_names[attr]
            
            if isinstance(attr_obj.special, CombinedSpecial):
                # FIXME: Generalize it to generic combinations
                builder.add_attribute(lookups.attr_names['intern_ip'])
                builder.add_attribute(lookups.attr_names['additional_ips'],
                        True)
                cond1 = builder.get_filter_sql('additional_ips', f)
                cond2 = builder.get_filter_sql('intern_ip', f)
                builder.sql_where.append(u'({0} OR {1})'.format(cond1, cond2))
            else:
                builder.add_attribute(attr_obj, isinstance(f, _Optional))
                builder.add_filter(attr_obj.name, f)


        # Copy order_by from instance to local variable to allow LIMIT
        # to set it in the query (but not in the instance) if it is
        # not set
        order_by = self._order_by
        order_dir = self._order_dir

        # Add LIMIT
        if self._limit:
            if not order_by:
                order_by = u'hostname'
                order_dir = u'asc'
            builder.add_limit(self._offset, self._limit)
        
        if order_by:
            attr_obj = lookups.attr_names[order_by]
            builder.add_attribute(attr_obj, optional=True)
            builder.add_ordering((order_by, order_dir))
        
        for attr in ('object_id', 'hostname', 'intern_ip', 'segment', 'servertype'):
            builder.add_attribute(lookups.attr_names[attr])
            builder.add_select(attr)
        builder.sql_keywords += ['SQL_CALC_FOUND_ROWS', 'DISTINCT']
        sql_stmt = builder.build_sql()

        c = connection.cursor()
        c.execute(sql_stmt)
        server_data = {}
        servertype_lookup = dict((k, v.name) for k, v in
                lookups.stype_ids.iteritems())
        restrict = self._restrict
        for server_id, hostname, intern_ip, segment, stype in c.fetchall():
            if not restrict:
                attrs = {
                    u'hostname': hostname,
                    u'intern_ip': IP(intern_ip),
                    u'segment': segment,
                    u'servertype': servertype_lookup[stype]
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
            
            server_object = ServerObject(attrs, server_id, self)
            server_data[server_id] = server_object
            
            for attr in lookups.stype_ids[stype].attributes:
                if attr.multi:
                    if not restrict or attr.name in restrict:
                        dict.__setitem__(server_object, attr.name, set())

        c.execute('SELECT FOUND_ROWS()')
        self._num_rows = c.fetchone()[0]
        
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
        c = connection.cursor()
        server_ids = u', '.join(map(str, server_data.iterkeys()))
        sql_stmt = (u'SELECT server_id, attrib_id, value FROM attrib_values '
                    u'WHERE server_id IN({0})').format(server_ids)
        
        if restrict:
            restrict_ids = u', '.join(str(lookups.attr_names[attr_name].pk)
                    for attr_name in restrict)
            sql_stmt += u' AND attrib_id IN({0})'.format(restrict_ids)
       
        c.execute(sql_stmt)
        attr_ids = lookups.attr_ids
        for server_id, attr_id, value in c.fetchall():
            attr = attr_ids[attr_id]
            attr_type = attr.type
            if attr_type == u'integer':
                value = int(value)
            elif attr_type == u'boolean':
                value = value == '1'
            elif attr_type == u'ip':
                value = IP(value)

            # Using dict-methods to bypass ServerObject's special properties
            if attr.multi:
                # Bypass MultiAttr wrapping in ServerObject.__getitem__
                dict.__getitem__(server_data[server_id], attr.name).add(value)
            else:
                dict.__setitem__(server_data[server_id], attr.name, value)
    
    def _cache_pre_store(self, server_data):
        return server_data

    def _cache_post_load(self, server_data):
        for server in server_data.itervalues():
            server._queryset = self
        return server_data

class ServerObject(BaseServerObject):
    def commit(self):
        commit = self._build_commit_object()
        commit_changes(commit)
        self._confirm_changes()

    def __reduce__(self):
        # Just pickle it as normal dict
        tpl = dict.__reduce__(self)
        instance_dict = tpl[2].copy()
        del instance_dict[u'_queryset']
        return (tpl[0], tpl[1], instance_dict)
