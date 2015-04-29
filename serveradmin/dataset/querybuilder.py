from datetime import datetime

from adminapi.utils import IP, IPv6
from serveradmin.dataset.base import lookups, ServerTableSpecial, CombinedSpecial

class QueryBuilder(object):
    def __init__(self):
        self.uid = 0
        self.aliases = {}
        self.sql_select = []
        self.sql_keywords = []
        self.sql_left_joins = []
        self.sql_from_tables = []
        self.sql_where = []
        self.sql_limit = []
        self.sql_order_by = []
        self.sql_group_by = []
        self.sql_extra = []

    def get_uid(self):
        self.uid += 1
        return self.uid

    def add_attribute(self, attr, optional=False, alias=None):
        attr_obj = lookups.attr_names[attr]

        if alias is None:
            alias = attr_obj.name

        if alias in self.aliases:
            return self.aliases[alias]

        if isinstance(attr_obj.special, ServerTableSpecial):
            attr_field = u'adms.' + attr_obj.special.field
        elif isinstance(attr_obj.special, CombinedSpecial):
            attr_field = None
            for extra_attr in attr_obj.special.attrs:
                self.add_attribute(extra_attr, optional=True)
        else:
            uid = self.get_uid()

            attr_field = u'av{0}.value'.format(uid)
            if optional:
                join = (u'LEFT JOIN attrib_values AS av{0} '
                        u'ON av{0}.server_id = adms.server_id AND '
                        u'av{0}.attrib_id = {1}').format(uid, attr_obj.pk)
                self.sql_left_joins.append(join)
            else:
                self.sql_from_tables.append(u'attrib_values AS av{0}'.format(
                        uid))
                where = (u'av{0}.server_id = adms.server_id AND '
                         u'av{0}.attrib_id = {1}').format(uid, attr_obj.pk)
                self.sql_where.append(where)

        self.aliases[alias] = {'attr': attr_obj, 'field': attr_field}
        return self.aliases[alias]

    def get_filter_sql(self, alias, filter_obj):
        alias_info = self.aliases[alias]
        attr_field = alias_info['field']
        attr_obj = alias_info['attr']

        if isinstance(attr_obj.special, CombinedSpecial):
            conds = []
            for attr in attr_obj.special.attrs:
                extra = self.aliases[attr]
                conds.append(filter_obj.as_sql_expr(self, extra['attr'],
                    extra['field']))
            return u'({0})'.format(u' OR '.join(conds))
        else:
            return filter_obj.as_sql_expr(self, attr_obj, attr_field)

    def add_filter(self, alias, filter_obj):
        self.sql_where.append(self.get_filter_sql(alias, filter_obj))

    def add_ordering(self, ordering):
        alias, direction = ordering
        direction = 'DESC' if direction.lower() == 'desc' else 'ASC'
        attr_field = self.aliases[alias]['field']
        self.sql_order_by.append(u'{0} {1}'.format(attr_field, direction))

    def add_select(self, *aliases):
        for alias in aliases:
            field = self.aliases[alias]['field']
            attr_obj = self.aliases[alias]['attr']
            if isinstance(attr_obj.special, CombinedSpecial):
                self.add_select(*attr_obj.special.attrs)
            else:
                self.sql_select.append(field)

    def add_limit(self, offset, limit):
        self.sql_limit = [offset, limit]

    def add_group_by(self, *aliases):
        for alias in aliases:
            self.sql_group_by.append(self.aliases[alias]['field'])

    def build_sql(self):
        self.sql_from_tables.append(u'admin_server AS adms')
        keywords = u' '.join(self.sql_keywords)
        select = u', '.join(self.sql_select)
        from_tables = u', '.join(self.sql_from_tables)
        left_joins = u'\n'.join(self.sql_left_joins)
        where = u' AND '.join(self.sql_where)
        order_by = u', '.join(self.sql_order_by)
        group_by = u', '.join(self.sql_group_by)

        sql = []
        if not select:
            raise ValueError('You have to supply select fields')
        sql.append(u'SELECT ' + keywords + ' ' + select)
        sql.append(u'FROM ' + from_tables)
        if left_joins:
            sql.append(left_joins)
        if where:
            sql.append(u'WHERE ' + where)
        if order_by:
            sql.append(u'ORDER BY ' + order_by)
        if group_by:
            sql.append(u'GROUP BY ' + group_by)
        if self.sql_extra:
            sql.append(self.sql_extra)
        if self.sql_limit:
            sql.append(u'LIMIT {0}, {1}'.format(*self.sql_limit))

        sql_stmt = u'\n'.join(sql)
        return sql_stmt

# Note: This function is also inlined in queryset.py for performance
def typecast_attribute(attr_name, value):
    attr_type = lookups.attr_names[attr_name].type

    if attr_type == u'integer':
        return int(value)
    elif attr_type == u'boolean':
        return value == '1'
    elif attr_type == u'ip':
        return IP(value)
    elif attr_type == u'ipv6':
        return IPv6.from_hex(value)
    elif attr_type == u'datetime':
        return datetime.fromtimestamp(int(value))
    else:
        return value
