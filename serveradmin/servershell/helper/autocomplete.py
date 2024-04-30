from django.db import ProgrammingError, connection

from serveradmin.serverdb.models import Attribute, Server, ServerAttribute


def attribute_startswith(search_string, limit=20):
    """Query attributes starting search_string

    :param search_string: e.g. al to match allow_from, allow_to etc.
    :param limit: limit result to n results

    :return:
    """

    query = (
        Attribute.objects.filter(attribute_id__startswith=search_string).only('attribute_id').order_by('attribute_id')
    )
    attributes = [attribute.attribute_id for attribute in query[:limit]]

    for attribute in Attribute.specials.keys():
        if attribute.startswith(search_string):
            attributes.append(attribute)

    return sorted(attributes[:limit])


def attribute_value_startswith(attribute_id, search_string, limit=20):
    """Query attribute for values starting with search string

    :param attribute_id: e.g. servertype or primary_ip6
    :param search_string: e.g. 2a00:
    :param limit: limit result to n results
    :return:
    """

    if attribute_id in Attribute.specials.keys():
        return _specials_value_startswith(attribute_id, search_string, limit)
    else:
        return _value_startswith(attribute_id, search_string, limit)


def _specials_value_startswith(attribute_id, search_string, limit=20):
    """Query attribute specials starting with search_string

    :param attribute_id: e.g. servertype
    :param search_string: e.g. v
    :param limit: limit result to n results
    :return:
    """

    column_name = Attribute.specials[attribute_id].special.field

    with connection.cursor() as cursor:
        # This is safe because field_name comes from us
        sql = 'SELECT DISTINCT {} FROM server WHERE {} LIKE %s ORDER BY {} ASC LIMIT {}'.format(
            column_name, column_name, column_name, limit
        )
        # This MUST be escaped to prevent SQL injection
        try:
            cursor.execute(sql, [search_string + '%'])
            return [row[0] for row in cursor.fetchall()]
        except ProgrammingError:
            # Invalid attribute name or type like intran_ip
            return []


def _value_startswith(attribute_id, search_string, limit=20):
    """Query attribute starting with search_string

    :param attribute_id: e.g. primary_ip6
    :param search_string: e.g. 2a00
    :param limit: e.g. limit result to n results
    :return:
    """

    query_attribute = Attribute.objects.filter(attribute_id=attribute_id)
    if not query_attribute:
        return []

    attribute = query_attribute.first()
    attribute_model = ServerAttribute.get_model(attribute.type)

    if attribute.type == 'reverse':
        # Should not be queried by client but lets be sure.
        return []

    if attribute.type == 'relation':
        query = (
            Server.objects.filter(servertype_id=attribute_id)
            .filter(hostname__startswith=search_string)
            .only('hostname')
            .order_by('hostname')
        )
        return [server.hostname for server in query[:limit]]
    if attribute.type == 'boolean':
        return ['true', 'false']

    query = (
        attribute_model.objects.filter(attribute_id=attribute_id)
        .filter(value__startswith=search_string)
        .only('value')
        .distinct('value')
        .order_by('value')
    )
    return [attr.value for attr in query[:limit]]
