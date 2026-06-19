"""Serveradmin - SQL Generator

Copyright (c) 2019 InnoGames GmbH
"""
# XXX: It is terrible to generate SQL this way.  We should make this use
# parameterized queries at least.
# XXX: The code in this module is almost randomly split into functions.  Do
# not try to guess what they would do.

import itertools
from dataclasses import dataclass

from adminapi.filters import (
    All,
    Any,
    BaseFilter,
    Contains,
    ContainedBy,
    ContainedOnlyBy,
    Empty,
    FilterValueError,
    GreaterThan,
    GreaterThanOrEquals,
    LessThan,
    LessThanOrEquals,
    Overlaps,
    Regexp,
    StartsWith,
    Not,
)
from serveradmin.serverdb import models
from serveradmin.serverdb.models import (
    Server,
    ServerAttribute,
    ServerRelationAttribute, ServerInetAttribute, Attribute,
)
from serveradmin.serverdb.query_materializer import MAX_RELATED_DEPTH


@dataclass
class RelatedViaServertype:
    """How a single servertype resolves a related-via attribute.

    ``related_via_attribute`` is the relation the value is inherited through,
    or ``None`` when the servertype stores the attribute directly.
    ``override`` mirrors ``ServertypeAttribute.override_related_via``: when set,
    a directly stored value takes precedence over the inherited one, so both
    have to be considered.
    """
    related_via_attribute: object
    override: bool


@dataclass
class RelatedVia:
    """Related-via configuration of one attribute across all servertypes.

    ``scope`` are the servertypes the query is restricted to (the top of the
    resolution).  ``config`` maps every servertype that has the attribute to
    its :class:`RelatedViaServertype`, including those only reachable deeper in
    a related-via chain, so the resolution can recurse through multiple hops.
    """
    scope: set
    config: dict


# XXX: The "related_vias" argument is carried all the way through most of
# the functions to optimize related_via_attribute selection.  We should find
# a nicer way to achieve this.
def get_server_query(attribute_filters, related_vias):
    sql = (
        'SELECT'
        ' server.server_id,'
        ' server.hostname,'
        ' server.intern_ip,'
        ' server.servertype_id'
        ' FROM server'
    )
    if attribute_filters:
        sql += ' WHERE ' + ' AND '.join(
            _get_sql_condition(a, f, related_vias)
            for a, f in attribute_filters
        )
    sql += ' ORDER BY server.hostname'

    return sql


def _get_sql_condition(attribute, filt, related_vias):
    assert isinstance(filt, BaseFilter)

    if isinstance(filt, (Not, Any)):
        return _logical_filter_sql_condition(attribute, filt, related_vias)

    negate = False
    template = ''

    if attribute.type == 'boolean':
        # We have already dealt with the logical filters.  Other
        # complicated filters don't make any sense on booleans.
        if type(filt) != BaseFilter:
            raise FilterValueError(
                'Boolean attribute "{}" cannot be used with {}() filter'
                .format(attribute, type(filt).__name__)
            )
            if not isinstance(filt.value, bool):
                raise FilterValueError(
                    'Boolean attribute "{}" cannot be checked against {}'
                    .format(attribute, type(filt.value).__name__)
                )

        negate = not filt.value

    elif isinstance(filt, Regexp):
        template = '{0}::text ~ E' + _raw_sql_escape(filt.value)
    elif isinstance(filt, (GreaterThanOrEquals, LessThanOrEquals)):
        template = _basic_comparison_filter_template(attribute, filt)
    elif isinstance(filt, Overlaps):
        template = _containment_filter_template(attribute, filt)
    elif isinstance(filt, Empty):
        negate = True
        template = '{0} IS NOT NULL'
    else:
        template = '{0} = ' + _raw_sql_escape(filt.value)

    return _covered_sql_condition(attribute, template, negate, related_vias)


def _covered_sql_condition(attribute, template, negate, related_vias):
    if attribute.type in ['relation', 'reverse', 'supernet', 'domain']:
        template = (
            '{{0}} IN ('
            '   SELECT server_id'
            '   FROM server'
            '   WHERE {}'
            ')'
            .format(template.format('hostname'))
        )

    return (
        ('NOT ' if negate else '') +
        _condition_sql(attribute, template, related_vias)
    )


def _logical_filter_sql_condition(attribute, filt, related_vias):
    if isinstance(filt, Not):
        return 'NOT ({0})'.format(
            _get_sql_condition(attribute, filt.value, related_vias)
        )

    if isinstance(filt, All):
        joiner = ' AND '
    else:
        joiner = ' OR '

    if not filt.values:
        return 'NOT ({0})'.format(joiner.join(['true', 'false']))

    simple_values = []
    templates = []
    for value in filt.values:
        # Boolean attributes are stored as the mere existence of a row (no
        # "value" column), so they cannot be collected into an "IN (...)"
        # comparison.  Route them through _get_sql_condition() individually
        # to produce the proper EXISTS / NOT EXISTS conditions instead.
        if (
            type(filt) == Any
            and type(value) == BaseFilter
            and attribute.type != 'boolean'
        ):
            simple_values.append(value)
        else:
            templates.append(
                _get_sql_condition(attribute, value, related_vias)
            )

    if simple_values:
        if len(simple_values) == 1:
            template = _get_sql_condition(
                attribute, simple_values[0], related_vias
            )
        else:
            template = _covered_sql_condition(
                attribute,
                '{{0}} IN ({0})'.format(', '.join(
                    _raw_sql_escape(v.value) for v in simple_values
                )),
                False,
                related_vias,
            )
        templates.append(template)

    return '({0})'.format(joiner.join(templates))


def _basic_comparison_filter_template(attribute, filt):
    if isinstance(filt, GreaterThan):
        operator = '>'
    elif isinstance(filt, LessThan):
        operator = '<'
    elif isinstance(filt, GreaterThanOrEquals):
        operator = '>='
    else:
        operator = '<='

    return '{{}} {} {}'.format(
        operator, _raw_sql_escape(filt.value)
    )


def _containment_filter_template(attribute, filt):
    template = None     # To be formatted 2 times
    value = filt.value

    if attribute.type == 'inet':
        if isinstance(filt, StartsWith):
            template = "{{0}} >>= {0} AND host({{0}}) = host(0{})"
        elif isinstance(filt, Contains):
            template = "{{0}} >>= {0}"
        elif isinstance(filt, ContainedOnlyBy):
            template = "{{0}} << {0} AND NOT " + _supernet_exists_sql(
                attribute, 'supernet',
                '<< {0}',
                ('{{0}} << supernet.intern_ip',),
            )
        elif isinstance(filt, ContainedBy):
            template = "{{0}} <<= {0}"
        else:
            template = "{{0}} && {0}"

    elif attribute.type == 'string':
        if isinstance(filt, Contains):
            template = "{{0}} LIKE {0}"
            value = '{}{}{}'.format(
                '' if isinstance(filt, StartsWith) else '%', value, '%'
            )
        elif isinstance(filt, ContainedBy):
            template = "{0} LIKE '%%' || {{0}} || '%%'"

    if not template:
        raise FilterValueError(
            'Cannot use {} filter on "{}"'
            .format(type(filt).__name__, attribute)
        )

    return template.format(_raw_sql_escape(value))


def _target_servertype_sql(alias: str, attribute: models.Attribute) -> str:
    ids = list(
        attribute.target_servertype.values_list('servertype_id', flat=True)
    )
    if len(ids) == 1:
        return f"{alias}.servertype_id = '{ids[0]}'"
    return "{}.servertype_id IN ({})".format(
        alias, ', '.join("'{}'".format(i) for i in ids)
    )


def _condition_sql(attribute, template, related_vias):
    if attribute.special:
        return template.format('server.' + attribute.special.field)

    if attribute.type == 'supernet':
        return _supernet_exists_sql(
            attribute, 'supernet',
            '>>= server_addr.value',
            (
                _target_servertype_sql('supernet', attribute),
                template.format('supernet.server_id'),
            )
        )
    if attribute.type == 'domain':
        return _exists_sql(Server, 'sub', (
            _target_servertype_sql('sub', attribute),
            r"server.hostname ~ ('\A[^\.]+\.' || regexp_replace("
            r"sub.hostname, '(\*|\-|\.)', '\\\1', 'g') || '\Z')",
            template.format('sub.server_id'),
        ))
    if attribute.type == 'reverse':
        return _exists_sql(ServerRelationAttribute, 'sub', (
            "sub.attribute_id = '{0}'".format(attribute.reversed_attribute_id),
            'sub.value = server.server_id',
            template.format('sub.server_id'),
        ))

    return _real_condition_sql(attribute, template, related_vias)


def _real_condition_sql(attribute, template, related_vias):
    # If we come to this point, we must have the item for the entry existing
    # in the related-vias dictionary.  It carries the per-servertype resolution
    # configuration for the whole related-via chain.  If no servertype could
    # have matched, the caller must have returned an empty result before calling
    # this module.  No filter is optional in queries after all.
    related_via = related_vias[attribute.attribute_id]
    assert related_via.config

    # Aliases must be unique because the resolution nests sub-queries (one per
    # related-via hop) that would otherwise shadow each other.
    aliases = itertools.count()
    return _resolve_related_via_sql(
        attribute, template, related_via.scope, related_via.config,
        sid_sql='server.server_id', servertype_sql='server.servertype_id',
        visited=frozenset(), depth=0, aliases=aliases,
    )


def _resolve_related_via_sql(
    attribute, template, scope, config, sid_sql, servertype_sql, visited,
    depth, aliases,
):
    """Build a condition true when the server identified by ``sid_sql``, whose
    servertype is one of ``scope``, has ``attribute`` resolved -- directly or
    through a related-via chain -- to a value matching ``template``.

    The attribute may resolve differently per servertype, so the in-scope
    servertypes are grouped by their configuration and each group contributes an
    OR'ed branch gated to the servertypes it applies to.  Related-via groups
    recurse into the source servers, following the relation one hop at a time.
    """
    # Group the in-scope servertypes by how they resolve the attribute so that
    # servertypes sharing a configuration share a single branch.
    groups = {}
    for servertype_id in scope:
        resolution = config.get(servertype_id)
        if resolution is None:
            continue
        related_via_attribute = resolution.related_via_attribute
        key = (
            related_via_attribute.attribute_id if related_via_attribute
            else None,
            resolution.override,
        )
        groups.setdefault(key, (resolution, []))[1].append(servertype_id)

    branches = []
    for resolution, servertype_ids in groups.values():
        conditions = []
        related_via_attribute = resolution.related_via_attribute

        # A directly stored value resolves the attribute when it is not related
        # via another one, or when this servertype may override the inherited
        # value with a direct one.
        if related_via_attribute is None or resolution.override:
            conditions.append(
                _direct_value_sql(attribute, template, sid_sql, aliases)
            )

        # An inherited value resolves it by following the relation to the source
        # server and resolving the attribute there in turn.
        if related_via_attribute is not None and depth < MAX_RELATED_DEPTH:
            hop = _related_hop_sql(
                attribute, template, related_via_attribute, config, sid_sql,
                visited, depth, aliases,
            )
            if hop is not None:
                conditions.append(hop)

        if not conditions:
            continue
        branch = (
            conditions[0] if len(conditions) == 1
            else '({0})'.format(' OR '.join(conditions))
        )

        # When several configurations coexist in the scope, each branch only
        # applies to the servertypes that actually use it.
        if len(groups) > 1:
            branch = '({0} AND {1})'.format(branch, _servertype_in_sql(
                sid_sql, servertype_sql, servertype_ids, aliases,
            ))
        branches.append(branch)

    if not branches:
        return 'false'
    if len(branches) == 1:
        return branches[0]
    return '({0})'.format(' OR '.join(branches))


def _direct_value_sql(attribute, template, sid_sql, aliases):
    """Condition: the server ``sid_sql`` stores ``attribute`` directly with a
    value matching ``template``."""
    model = ServerAttribute.get_model(attribute.type)
    assert model is not None
    alias = 'sub{0}'.format(next(aliases))
    return _exists_sql(model, alias, (
        '{0}.server_id = {1}'.format(alias, sid_sql),
        "{0}.attribute_id = '{1}'".format(alias, attribute.attribute_id),
        template.format('{0}.value'.format(alias)),
    ))


def _related_hop_sql(
    attribute, template, related_via_attribute, config, sid_sql, visited,
    depth, aliases,
):
    """Condition: the server ``sid_sql`` inherits ``attribute`` (matching
    ``template``) through ``related_via_attribute``, resolved recursively on the
    source server.

    Returns ``None`` to drop the branch when this exact (scope, relation) step
    has already been taken on the current path, which bounds the recursion for
    related-via configurations that would otherwise loop.
    """
    next_scope = _related_hop_scope(related_via_attribute, config)
    signature = (frozenset(next_scope), related_via_attribute.attribute_id)
    if signature in visited:
        return None
    next_visited = visited | {signature}

    def inner(next_sid):
        return _resolve_related_via_sql(
            attribute, template, next_scope, config, next_sid,
            servertype_sql=None, visited=next_visited, depth=depth + 1,
            aliases=aliases,
        )

    if related_via_attribute.type == 'supernet':
        alias = 'supernet{0}'.format(next(aliases))
        addr_alias = 'server_addr{0}'.format(alias)
        return _supernet_exists_sql(
            related_via_attribute, alias,
            '>>= {0}.value'.format(addr_alias),
            (
                _target_servertype_sql(alias, related_via_attribute),
                inner('{0}.server_id'.format(alias)),
            ),
            base_server_id=sid_sql,
            addr_alias=addr_alias,
            net_alias='net_addr{0}'.format(alias),
        )

    alias = 'rel{0}'.format(next(aliases))
    if related_via_attribute.type == 'reverse':
        # A reverse relation is followed against its direction: the source
        # server is the one whose forward relation points at ``sid_sql``.
        return _exists_sql(ServerRelationAttribute, alias, (
            "{0}.attribute_id = '{1}'".format(
                alias, related_via_attribute.reversed_attribute_id),
            '{0}.value = {1}'.format(alias, sid_sql),
            inner('{0}.server_id'.format(alias)),
        ))

    assert related_via_attribute.type == 'relation'
    return _exists_sql(ServerRelationAttribute, alias, (
        "{0}.attribute_id = '{1}'".format(
            alias, related_via_attribute.attribute_id),
        '{0}.server_id = {1}'.format(alias, sid_sql),
        inner('{0}.value'.format(alias)),
    ))


def _related_hop_scope(related_via_attribute, config):
    """Servertypes a related-via hop may resolve the attribute through: those
    that have the attribute and, when the relation declares its targets, that
    are among them."""
    have_attribute = set(config)
    target_ids = set(
        related_via_attribute.target_servertype
        .values_list('servertype_id', flat=True)
    )
    if target_ids:
        return have_attribute & target_ids
    return have_attribute


def _servertype_in_sql(sid_sql, servertype_sql, servertype_ids, aliases):
    """Condition restricting the server ``sid_sql`` to ``servertype_ids``.

    The top of the resolution has the servertype column at hand
    (``servertype_sql``); deeper hops reference the server by id only and look
    its servertype up instead."""
    in_list = ', '.join("'{0}'".format(s) for s in sorted(servertype_ids))
    if servertype_sql is not None:
        return '{0} IN ({1})'.format(servertype_sql, in_list)
    alias = 'srv{0}'.format(next(aliases))
    return _exists_sql(Server, alias, (
        '{0}.server_id = {1}'.format(alias, sid_sql),
        '{0}.servertype_id IN ({1})'.format(alias, in_list),
    ))


def _exists_sql(model, alias, conditions):
    return 'EXISTS (SELECT 1 FROM {0} AS {1} WHERE {2})'.format(
        model._meta.db_table, alias, ' AND '.join(c for c in conditions if c)
    )


def _supernet_exists_sql(
    attribute: Attribute, supernet_alias: str, addr_match: str,
    where: tuple[str, ...], base_server_id: str = 'server.server_id',
    addr_alias: str = 'server_addr', net_alias: str = 'net_addr',
):
    # The address aliases are parameterized so the helper can be nested inside
    # another related-via hop (resolving a supernet of a server other than the
    # outer one) without its aliases colliding.
    server_attr_alias = addr_alias + '_attr'
    net_attr_alias = net_alias + '_attr'
    if attribute.inet_address_family:
        af_join = (
            (Attribute._meta.db_table, server_attr_alias, (f'{server_attr_alias}.attribute_id = {addr_alias}.attribute_id',)),
            (Attribute._meta.db_table, net_attr_alias, (f'{net_attr_alias}.attribute_id = {net_alias}.attribute_id',)),
        )
        af_where = (
            f"{net_attr_alias}.inet_address_family = '{attribute.inet_address_family}'",
            f"{server_attr_alias}.inet_address_family = '{attribute.inet_address_family}'",
        )
    else:
        af_join = ()
        af_where = ()

    joins = (
        (ServerInetAttribute._meta.db_table, addr_alias, (f'{addr_alias}.server_id = {base_server_id}',)),
        (ServerInetAttribute._meta.db_table, net_alias, (
            f'{net_alias}.value ' + addr_match,
            f'{net_alias}.attribute_id = {addr_alias}.attribute_id',
            f'{net_alias}.server_id = {supernet_alias}.server_id',
        )),
    ) + af_join

    wheres = where + af_where

    return 'EXISTS (SELECT 1 FROM {0} AS {1} {2} WHERE {3})'.format(
        Server._meta.db_table,
        supernet_alias,
        ' '.join(f'JOIN {x[0]} AS {x[1]} ON ({" AND ".join(x[2])})' for x in joins),
        ' AND '.join(c for c in wheres)
    )


def _raw_sql_escape(value):
    try:
        value = str(value)
    except UnicodeEncodeError as error:
        raise FilterValueError(str(error))

    if "'" in value:
        raise FilterValueError('Single quote cannot be used')

    if value.endswith('\\'):
        raise FilterValueError(
            'Escape character cannot be used in the end'
        )

    value = value.replace('{', '{{').replace('}', '}}').replace('%', '%%')

    return "'" + value + "'"
