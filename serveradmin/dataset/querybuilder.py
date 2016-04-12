from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from serveradmin.dataset.base import lookups, ServerTableSpecial

class QueryBuilder(object):
    def __init__(self):
        self.uid = 0
        self.aliases = {}
        self.sql_select = []
        self.sql_keywords = []
        self.sql_left_joins = []
        self.sql_from_tables = []
        self.sql_where = []
        self.sql_order_by = []
        self.sql_limit = []
        self.sql_offset = []
        self.sql_extra = []

    def get_uid(self):
        self.uid += 1
        return self.uid

    def add_attribute(self, attr, optional=False, alias=None):
        attribute = lookups.attributes[attr]

        if alias is None:
            alias = attribute.pk

        if alias in self.aliases:
            return self.aliases[alias]

        if isinstance(attribute.special, ServerTableSpecial):
            attr_field = u'adms.' + attribute.special.field
        elif attribute.type == 'hostname' or attribute.multi:
            attr_field = None
        else:
            uid = self.get_uid()

            attr_field = u'av{0}.value'.format(uid)

            if optional:
                self.sql_left_joins.append((
                        u'LEFT JOIN attrib_values AS av{0} '
                        u'ON av{0}.server_id = adms.server_id AND '
                        u"av{0}.attrib_id = '{1}'"
                    ).format(uid, attribute.pk))

            else:
                self.sql_from_tables.append(
                        u'attrib_values AS av{0}'.format(uid)
                    )

                self.sql_where.append((
                        u'av{0}.server_id = adms.server_id AND '
                        u"av{0}.attrib_id = '{1}'"
                    ).format(uid, attribute.pk))

        self.aliases[alias] = {'attr': attribute, 'field': attr_field}
        return self.aliases[alias]

    def get_filter_sql(self, alias, filter_obj):
        alias_info = self.aliases[alias]
        attr_field = alias_info['field']
        attribute = alias_info['attr']

        return filter_obj.as_sql_expr(self, attribute, attr_field)

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
            attribute = self.aliases[alias]['attr']
            self.sql_select.append(field)

    def add_limit(self, limit):
        self.sql_limit = limit

    def add_offset(self, offset):
        self.sql_offset = offset

    def build_sql(self):
        self.sql_from_tables.append(u'admin_server AS adms')
        keywords = u' '.join(self.sql_keywords)
        select = u', '.join(self.sql_select)
        from_tables = u', '.join(self.sql_from_tables)
        left_joins = u'\n'.join(self.sql_left_joins)
        where = u' AND '.join(self.sql_where)
        order_by = u', '.join(self.sql_order_by)

        sql = []
        sql.append(u'SELECT ' + keywords + ' ' + select)
        sql.append(u'FROM ' + from_tables)
        if left_joins:
            sql.append(left_joins)
        if where:
            sql.append(u'WHERE ' + where)
        if order_by:
            sql.append(u'ORDER BY ' + order_by)
        if self.sql_extra:
            sql.append(self.sql_extra)
        if self.sql_limit:
            sql.append(u'LIMIT ' + str(self.sql_limit))
        if self.sql_offset:
            sql.append(u'OFFSET ' + str(self.sql_offset))

        sql_stmt = u'\n'.join(sql)
        return sql_stmt
