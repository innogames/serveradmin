from django.db import connection

from serveradmin.dataset.querybuilder import QueryBuilder, typecast_attribute

def get_attribute_values(attr_name, max_values=20):
    builder = QueryBuilder()
    try:
        builder.add_attribute(attr_name)
        builder.add_select(attr_name)
    except KeyError:
        return []

    builder.sql_keywords.append('DISTINCT')
    builder.add_limit(max_values)

    sql = builder.build_sql()

    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [typecast_attribute(attr_name, x[0]) for x in cursor.fetchall()]
