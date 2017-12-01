from serveradmin.dataset.filters import Any, BaseFilter, ExactMatch
from serveradmin.serverdb.models import Attribute


class QueryBuilder(object):
    def __init__(self, servertypes, filters):
        self.servertypes = servertypes
        self.sql_where = [
            Any(*(s.pk for s in servertypes))
            .as_sql_expr(Attribute.objects.get(pk='servertype'), servertypes)
        ]
        for attribute, value in filters.items():
            if not isinstance(value, BaseFilter):
                value = ExactMatch(value)
            self.sql_where.append(value.as_sql_expr(attribute, servertypes))

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
