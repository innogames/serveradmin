class QueryBuilder(object):
    def __init__(self):
        self.sql_where = []

    def add_filter(self, attribute, servertypes, filter_obj):
        self.sql_where.append(filter_obj.as_sql_expr(attribute, servertypes))

    def build_sql(self):
        sql = []
        sql.append(
            'SELECT'
            '   server.server_id,'
            '   server.hostname,'
            '   server.intern_ip,'
            '   server.segment_id AS _segment_id,'
            '   server.servertype_id AS _servertype_id,'
            '   server.project_id AS _project_id'
        )
        sql.append('FROM server')
        if self.sql_where:
            sql.append('WHERE {0}'.format(' AND '.join(self.sql_where)))

        return '\n'.join(sql)
