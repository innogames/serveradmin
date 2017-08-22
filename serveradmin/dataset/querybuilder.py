class QueryBuilder(object):
    def __init__(self, servertypes, filters):
        self.servertypes = servertypes
        self.sql_where = [
            f.as_sql_expr(a, self.servertypes)
            for a, f in filters.items()
        ]

    def build_sql(self):
        sql = []
        sql.append(
            'SELECT'
            '   server.server_id,'
            '   server.hostname,'
            '   server.intern_ip,'
            '   server.servertype_id AS _servertype_id,'
            '   server.project_id AS _project_id'
        )
        sql.append('FROM server')
        if self.sql_where:
            sql.append('WHERE {0}'.format(' AND '.join(self.sql_where)))

        return '\n'.join(sql)
