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
    def __init__(self, filters, restrict, augmentations):
        self.filters = filters
        self.restrict = restrict
        self.augmentations = augmentations
    
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
        
        return True

class QuerySet(BaseQuerySet):
    def __init__(self, filters, for_export=False):
        for attr in filters:
            if attr not in lookups.attr_names:
                raise ValueError('Invalid attribute: {0}'.format(attr))
        BaseQuerySet.__init__(self, filters)
        self.attributes = lookups.attr_names
        self._for_export = for_export
        self._already_through_cache = False
        self._limit = None
        self._offset = None

    def commit(self):
        commit = self._build_commit_object()
        commit_changes(commit)
        self._confirm_changes()

    def get_raw_results(self):
        self._get_results()
        return self._results

    def get_representation(self):
        return QuerySetRepresentation(self._filters, self._restrict,
                self._augmentations)

    def limit(self, offset, limit=None):
        if limit is None:
            self._limit = offset
            self._offset = 0
        else:
            self._limit = limit
            self._offset = offset
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
                cacher = QuerysetCacher(self, 'qs',
                        pre_store=self._cache_pre_store,
                        post_load=self._cache_post_load)
                self._results = cacher.get_results()

    def _fetch_results(self):
        # XXX: Dirty hack for the old database structure
        attr_exceptions = {
                'hostname': 'hostname', 
                'intern_ip': 'intern_ip',
                'segment': 'segment',
                'servertype': 'servertype_id',
                'object_id': 'server_id'
        }
        i = 0
        sql_left_joins = []
        sql_from = ['admin_server AS adms']
        sql_where = []
        attr_names = lookups.attr_names
        all_ips = self._filters.get('all_ips')
        _Optional = filters.Optional
        if all_ips:
            del self._filters['all_ips']
        for attr, f in self._filters.iteritems():
            if attr in attr_exceptions:
                attr_field = attr_exceptions[attr]
                if isinstance(f, _Optional):
                    sql_where.append('({0} IS NULL OR {1})'.format(attr_field,
                        f.as_sql_expr(attr, attr_field)))
                else:
                    sql_where.append(f.as_sql_expr(attr, attr_field))
            else:
                attr_field = 'av{0}.value'.format(i)
                if isinstance(f, _Optional):
                    join = ('LEFT JOIN attrib_values AS av{0} '
                            'ON av{0}.server_id = adms.server_id AND '
                            'av{0}.attrib_id = {1}').format(i,
                                attr_names[attr].pk)
                    sql_left_joins.append(join)
                    sql_where.append('({0} IS NULL OR {1})'.format(attr_field,
                            f.as_sql_expr(attr, attr_field)))

                else:
                    sql_from.append('attrib_values AS av{0}'.format(i))
                    sql_where += [
                        'av{0}.server_id = adms.server_id'.format(i),
                        'av{0}.attrib_id = {1}'.format(i, attr_names[attr].pk),
                        f.as_sql_expr(attr, attr_field)
                    ]
        
                i += 1

        if all_ips:
            attr_field = 'av{0}.value'.format(i)
            attr_id = attr_names['additional_ips'].pk
            join = ('LEFT JOIN attrib_values AS av{0} '
                    'ON av{0}.server_id = adms.server_id AND '
                    'av{0}.attrib_id = {1}').format(i, attr_id)
            sql_left_joins.append(join)
            cond1 = all_ips.as_sql_expr('additional_ips', attr_field)
            cond2 = all_ips.as_sql_expr('intern_ip', 'intern_ip')
            sql_where.append('(({0}) OR {1})'.format(cond1, cond2))
        
        if self._limit:
            limit_extra = 'ORDER BY adms.hostname\nLIMIT {0}, {1}'.format(
                    self._offset, self._limit)
        else:
            limit_extra = ''
        sql_stmt = '\n'.join([
                'SELECT adms.server_id, adms.hostname, adms.intern_ip, '
                'adms.segment, adms.servertype_id',
                'FROM',
                ', '.join(sql_from),
                '\n'.join(sql_left_joins),
                'WHERE' if sql_where else '',
                '\n AND '.join(sql_where),
                'GROUP BY adms.server_id',
                limit_extra
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
                if 'hostname' in restrict:
                    attrs[u'hostname'] = hostname
                if 'intern_ip' in restrict:
                    attrs[u'intern_ip'] = IP(intern_ip)
                if 'segment' in restrict:
                    attrs[u'segment'] = segment
                if 'servertype' in restrict:
                    attrs[u'servertype'] = servertype_lookup[stype]
            
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
        server_ids = ', '.join(map(str, server_data.iterkeys()))
        sql_stmt = ('SELECT server_id, attrib_id, value FROM attrib_values '
                    'WHERE server_id IN({0})').format(server_ids)
        
        if restrict:
            restrict_ids = ', '.join(str(lookups.attr_names[attr_name].pk)
                    for attr_name in restrict)
            sql_stmt += ' AND attrib_id IN({0})'.format(restrict_ids)
        
        c.execute(sql_stmt)
        attr_ids = lookups.attr_ids
        for server_id, attr_id, value in c.fetchall():
            attr = attr_ids[attr_id]
            attr_type = attr.type
            if attr_type == 'integer':
                value = int(value)
            elif attr_type == 'boolean':
                value = value == '1'
            elif attr_type == 'ip':
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
        del instance_dict['_queryset']
        return (tpl[0], tpl[1], instance_dict)
