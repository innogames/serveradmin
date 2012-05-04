from django.db import connection

from adminapi.dataset.base import BaseQuerySet, BaseServerObject
from adminapi.utils import IP
from serveradmin.dataset.base import lookups
from serveradmin.dataset.filters import Optional as _Optional, _prepare_filter

class QuerySet(BaseQuerySet):
    def commit(self):
        print 'I am not implemented yet, but would normally commit changes'
        self._confirm_changes()

    def get_raw_results(self):
        self._get_results()
        return self._results

    def _fetch_results(self):
        attr_exceptions = frozenset(['hostname', 'intern_ip', 'segment'])
        i = 0
        sql_left_joins = []
        sql_from = ['admin_server AS adms']
        sql_where = []
        attr_names = lookups.attr_names
        for attr, f in self._filters.iteritems():
            if attr in attr_exceptions:
                attr_field = attr
                if isinstance(f, _Optional):
                    sql_where.append('({0} IS NULL OR {1})'.format(attr_field,
                        f.as_sql_expr(attr_field)))
                else:
                    sql_where.append(f.as_sql_expr(attr_field))
            else:
                attr_field = 'av{0}.value'.format(i)
                if isinstance(f, _Optional):
                    join = ('LEFT JOIN attrib_values AS av{0} '
                            'ON av{0}.server_id = adms.server_id AND '
                            'av{0}.attrib_id = {1} AND {2}').format(i,
                                attr_names[attr].pk, f.as_sql_expr(attr_field))
                    sql_left_joins.append(join)
                else:
                    sql_from.append('attrib_values AS av{0}'.format(i))
                    sql_where += [
                        'av{0}.server_id = adms.server_id'.format(i),
                        'av{0}.attrib_id = {1}'.format(i, attr_names[attr].pk),
                        f.as_sql_expr(attr_field)
                    ]
        
                i += 1
        
        sql_stmt = '\n'.join([
                'SELECT adms.server_id, adms.hostname, adms.intern_ip, '
                'adms.segment, adms.servertype_id',
                'FROM',
                ', '.join(sql_from),
                '\n'.join(sql_left_joins),
                'WHERE' if sql_where else '',
                '\n AND '.join(sql_where),
                'GROUP BY adms.server_id'
        ])

        servertype_lookup = dict((stype.pk, stype.name) for stype in
                ServerType.objects.all())

        c = connection.cursor()
        
        c.execute(sql_stmt)
        server_data = {}
        for server_id, hostname, intern_ip, segment, stype in c.fetchall():
            server_data[server_id] = ServerObject({
                u'object_id': server_id,
                u'hostname': hostname,
                u'intern_ip': IP(intern_ip),
                u'segment': segment,
                u'servertype': servertype_lookup[stype]
            }, server_id, self)
        
        # Return early if there are no servers (= empty dict)
        if not server_data:
            return server_data
        
        server_ids = ', '.join(map(str, server_data.iterkeys()))
        sql_stmt = ('SELECT server_id, attrib_id, value FROM attrib_values '
                    'WHERE server_id IN({0})').format(server_ids)
        
        if self._restrict:
            attr_lookup_names = dict((v.name, k) for k, v in
                    attr_lookup.iteritems())
            restrict_ids = ', '.join(str(attr_lookup_names[attr_name])
                    for attr_name in self._restrict)
            sql_stmt += ' AND attrib_id IN({0})'.format(restrict_ids)

        c.execute(sql_stmt)
        for server_id, attr_id, value in c.fetchall():
            attr = attr_lookup[attr_id]
            attr_type = attr.type
            if attr_type == 'integer':
                value = int(value)
            elif attr_type == 'boolean':
                value = value == '1'
            elif attr_type == 'ip':
                value = IP(value)
            
            # Using dict-methods to bypass ServerObject's special properties
            if attr.multi:
                values = dict.setdefault(server_data[server_id], attr.name, set())
                values.add(value)
            else:
                dict.__setitem__(server_data[server_id], attr.name, value)
        
        return server_data

class ServerObject(BaseServerObject):
    def commit(self):
        print 'I am not implemented yet, but would normally commit changes'
        self._confirm_changes()

def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.iteritems())
    return QuerySet(filters)
