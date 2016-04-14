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

        self.sql_order_by.append(u'{0} {1}'.format(
            attribute.special.field,
            'DESC' if direction.upper() == 'DESC' else 'ASC',
        ))

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
                '   adms.server_id,'
                '   adms.hostname,'
                '   adms.intern_ip,'
                '   adms.segment_id,'
                '   adms.servertype_id,'
                '   adms.project_id'
            )

        sql.append(u'FROM admin_server AS adms')

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
