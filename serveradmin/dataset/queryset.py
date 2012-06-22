from django.db import connection

from adminapi.dataset.base import BaseQuerySet, BaseServerObject
from adminapi.utils import IP
from serveradmin.dataset.base import lookups
from serveradmin.dataset import filters
from serveradmin.dataset.commit import commit_changes
from serveradmin.dataset.cache import QuerysetCacher

CACHE_MIN_QS_COUNT = 3
NUM_OBJECTS_FOR_FILECACHE = 50

class QuerySetRepresentation(object):
    """ Object that can be easily pickled without storing to much data.
    The main use is to compare querysets for caching. 
    """
    def __init__(self, filters, restrict, augmentations, offset, limit,
                 order_by, order_dir):
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
    def __init__(self, filters, for_export=False):
        _check_attributes(filters.keys())
        super(QuerySet, self).__init__(filters)
        self.attributes = lookups.attr_names
        self._for_export = for_export
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
        _check_attributes(attrs)
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
        _check_attributes([order_by])
        if order_dir not in ('asc', 'desc'):
            raise ValueError('Invalid order direction')
        
        self._order_by = order_by
        self._order_dir = order_dir
        
        return self
    
    def _get_results(self):
        if self._results is not None:
            return
        if self._for_export:
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
        attr_exceptions = {
                u'hostname': u'hostname', 
                u'intern_ip': u'intern_ip',
                u'segment': u'segment',
                u'servertype': u'servertype_id',
                u'object_id': u'server_id'
        }
        i = 0
        sql_left_joins = []
        sql_from = [u'admin_server AS adms']
        sql_where = []
        attr_fields = {}
        attr_names = lookups.attr_names
        all_ips = self._filters.get(u'all_ips')
        _Optional = filters.Optional
        if all_ips:
            del self._filters[u'all_ips']
        for attr, f in self._filters.iteritems():
            if attr in attr_exceptions:
                attr_field = u'adms.' + attr_exceptions[attr]
                attr_fields[attr] = attr_field
                if isinstance(f, _Optional):
                    sql_where.append(u'({0} IS NULL OR {1})'.format(attr_field,
                        f.as_sql_expr(attr, attr_field)))
                else:
                    sql_where.append(f.as_sql_expr(attr, attr_field))
            else:
                attr_field = u'av{0}.value'.format(i)
                attr_fields[attr] = attr_field
                if isinstance(f, _Optional):
                    join = (u'LEFT JOIN attrib_values AS av{0} '
                            u'ON av{0}.server_id = adms.server_id AND '
                            u'av{0}.attrib_id = {1}').format(i,
                                attr_names[attr].pk)
                    sql_left_joins.append(join)
                    sql_where.append(u'({0} IS NULL OR {1})'.format(attr_field,
                            f.as_sql_expr(attr, attr_field)))

                else:
                    sql_from.append(u'attrib_values AS av{0}'.format(i))
                    sql_where += [
                        u'av{0}.server_id = adms.server_id'.format(i),
                        u'av{0}.attrib_id = {1}'.format(i, attr_names[attr].pk),
                        f.as_sql_expr(attr, attr_field)
                    ]
        
                i += 1

        if all_ips:
            attr_field = u'av{0}.value'.format(i)
            attr_fields[u'additional_ips'] = attr_field
            attr_id = attr_names[u'additional_ips'].pk
            join = (u'LEFT JOIN attrib_values AS av{0} '
                    u'ON av{0}.server_id = adms.server_id AND '
                    u'av{0}.attrib_id = {1}').format(i, attr_id)
            sql_left_joins.append(join)
            cond1 = all_ips.as_sql_expr(u'additional_ips', attr_field)
            cond2 = all_ips.as_sql_expr(u'intern_ip', u'intern_ip')
            sql_where.append(u'(({0}) OR {1})'.format(cond1, cond2))
            i += 1
        
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

            limit_sql = u'LIMIT {0}, {1}'.format(
                    self._offset, self._limit)
        else:
            limit_sql = u''
        
        # We will try to get the field name for ORDER BY. In case of the
        # field not being in the query, we will add it with a LEFT JOIN.
        if order_by:
            if order_by in attr_exceptions:
                order_field = u'adms.' + attr_exceptions[order_by]
            else:
                if order_by in attr_fields:
                    order_field = attr_fields[order_by]
                else:
                    attr_id = attr_names[order_by].pk
                    join = (u'LEFT JOIN attrib_values AS av{0} '
                            u'ON av{0}.server_id = adms.server_id AND '
                            u'av{0}.attrib_id = {1}').format(i, attr_id)
                    sql_left_joins.append(join)
                    order_field = u'av{0}.value'.format(i)

            order_by_sql = u'ORDER BY {0} {1}'.format(order_field,
                    order_dir.upper())
        else:
            order_by_sql = u''


        sql_stmt = u'\n'.join([
                u'SELECT SQL_CALC_FOUND_ROWS adms.server_id, adms.hostname, '
                u'adms.intern_ip, adms.segment, adms.servertype_id',
                u'FROM',
                u', '.join(sql_from),
                u'\n'.join(sql_left_joins),
                u'WHERE' if sql_where else '',
                u'\n AND '.join(sql_where),
                u'GROUP BY adms.server_id',
                order_by_sql,
                limit_sql
        ])

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
            restrict = restrict - set(attr_exceptions.iterkeys())
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

def _check_attributes(attributes):
    for attr in attributes:
        if attr not in lookups.attr_names:
            raise ValueError(u'Invalid attribute: {0}'.format(attr))
