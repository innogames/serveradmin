class QueryBuilder(object):
    def __init__(self):
        self.sql_where = []
        self.sql_order_by = []

    def add_filter(self, attribute, filter_obj):
        self.sql_where.append(filter_obj.as_sql_expr(attribute))

    def add_order_by(self, attribute, direction='ASC'):

        # Currently, we are only supporting ordering on the special
        # attributes.
        assert attribute.special

        field = attribute.special.field
        if field.startswith('_'):
            field = field[1:]

        self.sql_order_by.append(field + ' ' + direction.upper())

    def build_sql(self):
        sql = []
        sql.append(
            'SELECT'
            '   server.server_id,'
            '   server.hostname,'
            '   server.intern_ip,'
            '   server.segment_id,'
            '   server.servertype_id,'
            '   server.project_id'
        )
        sql.append('FROM server')
        if self.sql_where:
            sql.append('WHERE {0}'.format(' AND '.join(self.sql_where)))
        if self.sql_order_by:
            sql.append('ORDER BY {0}'.format(', '.join(self.sql_order_by)))

        return '\n'.join(sql)
