class QueryBuilder(object):
    def __init__(self):
        self.sql_where = []
        self.sql_order_by = []
        self.sql_limit = []
        self.sql_offset = []

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

    def add_limit(self, limit):
        self.sql_limit = limit

    def add_offset(self, offset):
        self.sql_offset = offset

    def build_sql(self, count=False):

        sql = []

        if count:
            sql.append('SELECT COUNT(*)')
        else:
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
            sql.append(u'WHERE {0}'.format(' AND '.join(self.sql_where)))

        if not count:
            if self.sql_order_by:
                sql.append('ORDER BY {0}'.format(', '.join(self.sql_order_by)))
            if self.sql_limit:
                sql.append('LIMIT {0}'.format(self.sql_limit))
            if self.sql_offset:
                sql.append('OFFSET {0}'.format(self.sql_offset))

        return '\n'.join(sql)
