"""Serveradmin - Query Executer

Copyright (c) 2018 InnoGames GmbH
"""

from django.core.exceptions import ValidationError
from django.db import DataError, connection, transaction

from serveradmin.serverdb.models import (
    Attribute,
    Servertype,
    ServertypeAttribute,
    Server,
)
from serveradmin.serverdb.sql_generator import get_server_query
from serveradmin.serverdb.query_materializer import QueryMaterializer


def execute_query(filters, restrict, order_by):
    """The main function to execute queries"""

    # REPEATABLE READ isolation level ensures Postgres to give us a consistent
    # snapshot for the database transaction.  We also set READ ONLY as this
    # is a query operation.  Perhaps this is also enabling some optimization
    # on the Postgres side.
    with transaction.atomic():
        connection.cursor().execute(
            'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
        )

        # The actual query execution procedure is 2 steps: first filtering
        # the objects, and then materializing the requested attributes.
        # The joined attributes and ordering are also handled on
        # the materialization step.  Ordering has to be handled by it, because
        # some properties of the attribute values which might be relevant
        # for ordering may be lost after the materialization.  See the query
        # materializer module for its details.  The functions on this module
        # continues with the filtering step.
        servers = _get_servers(filters)
        return list(QueryMaterializer(servers, restrict, order_by))


def _get_servers(filters):
    """Get the servers objects matching the filters

    In here, we would need a list of all possible servertypes that can match
    with the given query.  This is easy to find, because if a servertype
    doesn't have an attribute, the servers from this type can never be in
    a result of a query filtering by this attribute.
    """

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

    # If we have real attributes on the query filter, we can use them to
    # get the possible servertypes.  This is necessary to eliminate
    # not-desired objects.
    if real_attributes:
        servertypes = _get_possible_servertypes(real_attributes)
    else:
        servertypes = Servertype.objects.all()

    # If the servertype filter is also on the filters, we can deal with
    # it ourself.  This is only an optimization.
    if servertype_filt:
        servertypes = list(filter(
            lambda s: servertype_filt.matches(s.pk),
            servertypes,
        ))

    # If we found out that no servertype can match with the query only by
    # looking at the list of attributes used on the query filters, we can
    # take the short path and just return an empty list.
    if not servertypes:
        return []

    # If you managed to read this so far, the last step is refreshingly
    # easy: get and execute the raw SQL query.
    sql_query = get_server_query(servertypes, attribute_filters)
    try:
        return list(Server.objects.raw(sql_query))
    except DataError as error:
        raise ValidationError(error)


def _get_possible_servertypes(attributes):
    """Get the servertypes that can possible match with the query with
    the given attributes
    """

    # First, we need to index the servertypes by the attributes.
    attribute_servertypes = {}
    for sa in ServertypeAttribute.query(attributes=attributes).all():
        attribute_servertypes.setdefault(sa.attribute, set()).add(
            sa.servertype
        )

    # Then we get the servertype list of the first attribute, and continue
    # reducing it by getting intersection of the list of the next attribute.
    servertypes = attribute_servertypes.popitem()[1]
    for new in attribute_servertypes.values():
        servertypes = servertypes.intersection(new)

    return servertypes
