from collections import defaultdict

from django.db import connection, transaction

from serveradmin.serverdb.models import (
    Attribute,
    Servertype,
    ServertypeAttribute,
    Server,
)
from serveradmin.serverdb.sql_generator import get_server_query
from serveradmin.serverdb.query_materializer import QueryMaterializer


@transaction.atomic
def execute_query(filters, restrict, order_by):
    connection.cursor().execute(
        'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    )
    servers = _get_servers(filters)
    materializer = QueryMaterializer(servers, restrict, order_by)

    return list(materializer)


def _get_servers(filters):
    # We can just deal with the servertype filter ourself.
    if 'servertype' in filters:
        servertype_filt = filters.pop('servertype')
    else:
        servertype_filt = None

    attribute_filters = []
    real_attributes = []
    for attribute_id, filt in filters.items():
        attribute = Attribute.objects.get(pk=attribute_id)
        attribute_filters.append((attribute, filt))
        if not attribute.special:
            real_attributes.append(attribute)

    servertypes = _get_possible_servertypes(real_attributes)
    if servertype_filt:
        servertypes = list(filter(
            lambda s: servertype_filt.matches(s.pk),
            servertypes,
        ))

    if not servertypes:
        return []

    return Server.objects.raw(get_server_query(servertypes, attribute_filters))


def _get_possible_servertypes(attributes):
    servertypes = set(Servertype.objects.all())

    if attributes:
        attribute_servertypes = defaultdict(set)
        for sa in ServertypeAttribute.query(attributes=attributes).all():
            attribute_servertypes[sa.attribute].add(sa.servertype)

        for new in attribute_servertypes.values():
            servertypes = servertypes.intersection(new)

    return servertypes
