"""Serveradmin - Query Executer

Copyright (c) 2018 InnoGames GmbH
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
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

    # We need the restrict argument in slightly different structure.
    if restrict is None:
        joins = None
    else:
        joins = list(_get_joins(restrict))

    # We would need the attribute objects on this module and the depending
    # modules.  We start by collecting the attributes we need on all parts
    # of the query.
    attribute_ids = set(_collect_attribute_ids(joins, filters, order_by))
    attribute_ids.add('servertype')     # We may need "servertype" later.

    # We can fetch the attributes altogether before starting the database
    # transaction.  None on the restrict argument is special meaning
    # materialize all possible attributes, so we query them all.  The database
    # transaction doesn't have to be started yet, because the metadata like
    # the attributes are mostly stable, and the data model wouldn't let us
    # see anything in inconsistent state, even while it is being changed
    # concurrently.
    if restrict is None:
        attribute_lookup = _get_attribute_lookup()
    else:
        attribute_lookup = _get_attribute_lookup(attribute_ids)
    _check_attributes_exist(attribute_ids, attribute_lookup)

    servertypes = _get_servertypes(filters)
    if not servertypes:
        return []

    # Here we prepare the join dictionary for the query materializer.
    # For None on the restrict argument, we just use the complete list of
    # attributes prepared by the previous step.
    if restrict is None:
        materializer_args = [{a: None for a in attribute_lookup.values()}]
    else:
        def cast(join):
            return {
                attribute_lookup[a]: j if j is None else cast(j)
                for a, j in join
            }
        materializer_args = [cast(joins)]

    if order_by is not None:
        materializer_args.append([attribute_lookup[a] for a in order_by])

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
        servers = _get_servers(servertypes, filters, attribute_lookup)
        return list(QueryMaterializer(servers, *materializer_args))


def _get_joins(restrict):
    """Iterate the restrict clause with the joins"""

    for item in restrict:
        if isinstance(item, dict):
            if len(item) != 1:
                raise ValidationError('Malformatted join restriction')

            for attribute_id, join in item.items():
                yield (attribute_id, list(_get_joins(join)))
        else:
            yield (item, None)


def _collect_attribute_ids(joins=None, filters=None, order_by=None):
    """Yield the attribute_ids from all parts of the query"""

    if joins is not None:
        for attribute_id, join in joins:
            yield attribute_id

            for attribute_id in _collect_attribute_ids(join):
                yield attribute_id

    if filters is not None:
        for attribute_id in filters:
            yield attribute_id

    if order_by is not None:
        for attribute_id in order_by:
            yield attribute_id


def _get_attribute_lookup(attribute_ids=None):
    """Prepare the attribute lookup and make sure all exist"""

    return {
        a.pk: a
        for a in Attribute.objects.all()
        if attribute_ids is None or a.pk in attribute_ids
    }


def _check_attributes_exist(attribute_ids, attribute_lookup):
    """Check whether all required attribute ids are valid"""

    for attribute_id in attribute_ids:
        if attribute_id not in attribute_lookup:
            raise ObjectDoesNotExist('No attribute "{}"'.format(attribute_id))


def _get_servertypes(filters):
    """Get the servertype objects that can possible match with the filters

    In here, we would need a list of all possible servertypes that can match
    with the given query.  This is easy to find, because if a servertype
    doesn't have an attribute, the servers from this type can never be in
    a result of a query filtering by this attribute.
    """

    # If we have real attributes on the query filter, we can use them to
    # get the possible servertypes.  This is necessary to eliminate
    # not-desired objects.
    real_attribute_ids = [a for a in filters if a not in Attribute.specials]
    if real_attribute_ids:
        servertypes = _get_possible_servertypes(real_attribute_ids)
    else:
        servertypes = Servertype.objects.all()

    # If the servertype filter is also on the filters, we can deal with
    # it ourself.  This is only an optimization.
    if 'servertype' in filters:
        servertypes = list(filter(
            lambda s: filters['servertype'].matches(s.pk),
            servertypes,
        ))

    return servertypes


def _get_possible_servertypes(attribute_ids):
    """Get the servertypes that can possible match with the query with
    the given attributes
    """

    # First, we need to index the servertypes by the attributes.
    attribute_servertypes = {}
    for sa in ServertypeAttribute.objects.filter(
        _attribute_id__in=attribute_ids
    ):
        attribute_servertypes.setdefault(sa.attribute, set()).add(
            sa.servertype
        )

    # Then we get the servertype list of the first attribute, and continue
    # reducing it by getting intersection of the list of the next attribute.
    servertypes = attribute_servertypes.popitem()[1]
    for new in attribute_servertypes.values():
        servertypes = servertypes.intersection(new)

    return servertypes


def _get_servers(servertypes, filters, attribute_lookup):
    """Evaluate the filters to fetch the matching servers"""

    # From now on, we will pass the filters dictionary using the attribute
    # objects as the keys.  The SQL generator module will repeatedly need
    # the properties of the attributes.
    attribute_filters = []
    for attribute_id, filt in filters.items():
        attribute_filters.append((attribute_lookup[attribute_id], filt))

        # Before we actually execute the query, we can check the destiny of
        # the filters.  If one is destined to fail, we can just return empty
        # result.  If some are destined to pass, we can just remove them.
        # We could do this much earlier, even before preparing the attribute
        # lookup, but we don't because we still want to raise an error for
        # nonexistent attributes.
        destiny = filt.destiny()
        if destiny is False:
            return []
        if destiny is True:
            continue

        attribute_filters.append((attribute_lookup[attribute_id], filt))

    # If you managed to read this so far, the last step is refreshingly
    # easy: get and execute the raw SQL query.
    sql_query = get_server_query(servertypes, attribute_filters)
    try:
        return list(Server.objects.raw(sql_query))
    except DataError as error:
        raise ValidationError(error)
