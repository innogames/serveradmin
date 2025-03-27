"""Serveradmin - Query Executer

Copyright (c) 2019 InnoGames GmbH
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DataError, connection, transaction

from adminapi.filters import Any
from serveradmin.serverdb.models import Attribute, Server, ServertypeAttribute
from serveradmin.serverdb.query_materializer import QueryMaterializer
from serveradmin.serverdb.sql_generator import get_server_query


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

    # We can fetch the attributes altogether before starting the database
    # transaction.  None on the restrict argument is special meaning
    # materialize all possible attributes, so we query them all.  The database
    # transaction doesn't have to be started yet, because the metadata like
    # the attributes are mostly stable, and the data model wouldn't let us
    # see anything in inconsistent state, even while it is being changed
    # concurrently.  We start by the special attributes and fetch more
    # if necessary.
    attribute_lookup = dict(Attribute.specials)
    if restrict is None:
        _update_attribute_lookup(attribute_lookup)
    elif any(a not in attribute_lookup for a in attribute_ids):
        _update_attribute_lookup(attribute_lookup, attribute_ids)
    _check_attributes_exist(attribute_ids, attribute_lookup)

    # If we have real attributes on the query filter, we can use them to
    # get the possible servertypes.  This is necessary to eliminate
    # not-desired objects.  We also use them to eliminate the servertype
    # attribute relations passed to the SQL generator module in "related_vias".
    # This is an optimization that matters, because all of those in
    # "related_vias" hit the database as complicated sub-queries.
    related_vias = {}
    real_attribute_ids = [a for a in filters if a not in Attribute.specials]
    if real_attribute_ids:
        servertype_attributes = list(ServertypeAttribute.objects.filter(attribute_id__in=real_attribute_ids))
        servertype_ids = _get_possible_servertype_ids(servertype_attributes)
        filters = dict(filters)
        servertype_ids = _override_servertype_filter(filters, servertype_ids)
        servertype_attributes = [sa for sa in servertype_attributes if sa.servertype_id in servertype_ids]
        _update_related_vias(related_vias, servertype_attributes, attribute_lookup)

    # Here we prepare the join dictionary for the query materializer.
    # For None on the restrict argument, we just use the complete list of
    # attributes prepared by the previous step.
    if restrict is None:
        materializer_args = [{a: None for a in attribute_lookup.values()}]
    else:

        def cast(join):
            return {attribute_lookup[a]: j if j is None else cast(j) for a, j in join}

        materializer_args = [cast(joins)]

    if order_by is not None:
        materializer_args.append([attribute_lookup[a] for a in order_by])

    # REPEATABLE READ isolation level ensures Postgres to give us a consistent
    # snapshot for the database transaction.  We also set READ ONLY as this
    # is a query operation.  Perhaps this is also enabling some optimization
    # on the Postgres side.
    with transaction.atomic():
        connection.cursor().execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')

        # The actual query execution procedure is 2 steps: first filtering
        # the objects, and then materializing the requested attributes.
        # The joined attributes and ordering are also handled on
        # the materialization step.  Ordering has to be handled by it, because
        # some properties of the attribute values which might be relevant
        # for ordering may be lost after the materialization.  See the query
        # materializer module for its details.  The functions on this module
        # continues with the filtering step.
        servers = _get_servers(filters, attribute_lookup, related_vias)
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


def _update_attribute_lookup(attribute_lookup, attribute_ids=None):
    if attribute_ids is None:
        queryset = Attribute.objects.all()
    else:
        queryset = Attribute.objects.filter(attribute_id__in=attribute_ids)

    for attribute in queryset:
        attribute_lookup[attribute.attribute_id] = attribute


def _check_attributes_exist(attribute_ids, attribute_lookup):
    """Check whether all required attribute ids are valid"""

    for attribute_id in attribute_ids:
        if attribute_id not in attribute_lookup:
            raise ObjectDoesNotExist('No attribute "{}"'.format(attribute_id))


def _get_possible_servertype_ids(servertype_attributes):
    """Get the servertypes that can possible match with the query with
    the given attributes

    In here, we would need a list of all possible servertypes that can match
    with the given query.  This is easy to find, because if a servertype
    doesn't have an attribute, the servers from this type can never be in
    a result of a query filtering by this attribute.
    """

    # First, we need to index the servertypes by the attributes.
    attribute_servertype_ids = {}
    for sa in servertype_attributes:
        ids = attribute_servertype_ids.setdefault(sa.attribute_id, set())
        ids.add(sa.servertype_id)

    # Then we get the servertype list of the first attribute, and continue
    # reducing it by getting intersection of the list of the next attribute.
    servertype_ids = attribute_servertype_ids.popitem()[1]
    for new in attribute_servertype_ids.values():
        servertype_ids = servertype_ids.intersection(new)

    return servertype_ids


def _override_servertype_filter(filters, servertype_ids):
    """Override the servertype filter using the possible servertypes"""

    # If the servertype filter is also on the filters, we can deal with
    # it ourself.  This is an optimization.  We could not do this, but
    # then we wouldn't be able to override the same filter.
    if 'servertype' in filters:
        servertype_ids = [s for s in servertype_ids if filters['servertype'].matches(s)]

    # Here we add the servertype filter or override the existing one.
    filters['servertype'] = Any(*servertype_ids)

    return servertype_ids


def _update_related_vias(related_vias, servertype_attributes, attribute_lookup):
    """Prepare the related_vias dictionary for the SQL generator module

    It is lists in dictionaries of dictionaries indexed first by attribute_id
    and then by the related_via_attribute.  The attribute lookup dictionary
    passed to here may not have all of the related via attributes we need.
    In this case we recursively query them and repeat the process for
    the remaining object.
    """
    to_be_looked_up = []
    for sa in servertype_attributes:
        related_via_attribute_id = sa.related_via_attribute_id
        if not related_via_attribute_id:
            related_via_attribute = None
        elif related_via_attribute_id not in attribute_lookup:
            to_be_looked_up.append(sa)
            continue
        else:
            related_via_attribute = attribute_lookup[related_via_attribute_id]

        (related_vias.setdefault(sa.attribute_id, {}).setdefault(related_via_attribute, []).append(sa.servertype_id))

    if to_be_looked_up:
        _update_attribute_lookup(
            attribute_lookup,
            {sa.related_via_attribute_id for sa in to_be_looked_up},
        )
        _update_related_vias(related_vias, to_be_looked_up, attribute_lookup)


def _get_servers(filters, attribute_lookup, related_vias):
    """Evaluate the filters to fetch the matching servers"""

    # From now on, we will pass the filters dictionary using the attribute
    # objects as the keys.  The SQL generator module will repeatedly need
    # the properties of the attributes.
    attribute_filters = []
    for attribute_id, filt in filters.items():
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
    sql_query = get_server_query(attribute_filters, related_vias)
    try:
        return list(Server.objects.defer('intern_ip').raw(sql_query))
    except DataError as error:
        raise ValidationError(error)
