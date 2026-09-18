"""Serveradmin - SQL Generator

Copyright (c) 2019 InnoGames GmbH
"""
# XXX: It is terrible to generate SQL this way.  We should make this use
# parameterized queries at least.
# XXX: The code in this module is almost randomly split into functions.  Do
# not try to guess what they would do.

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
    model = ServerAttribute.get_model(attribute.type)
    assert model is not None

    # If we come to this point, we must have the item for the entry existing
    # in the related-vias dictionary.  Keep in mind that it also includes
    # the directly attached servertype attribute combinations.  They would
    # have None as the key of the inner dictionary.  If no servertype attribute
    # combinations had been possible, the caller must have returned an empty
    # result, before calling this module to get the SQL query.  No filter
    # is optional in queries after all.
    related_vias = related_vias[attribute.attribute_id]
    assert related_vias

    attribute_conditions = (
        "sub.attribute_id = '{0}'".format(attribute.attribute_id),
        template.format('sub.value'),
    )

    # One condition per relation path.  The directly attached path stays a
    # correlated EXISTS: with a single equality to "server" Postgres turns
    # it into a hash semi join, or an anti join under NOT.  The inherited
    # paths are deliberately *uncorrelated* subqueries instead - see
    # _inherited_server_ids_sql() for why.
    path_conditions = []
    for related_via_attribute, servertype_ids in related_vias.items():
        if related_via_attribute is None:
            condition = _exists_sql(
                model, 'sub',
                ('server.server_id = sub.server_id',) + attribute_conditions,
            )
        else:
            condition = '(server.server_id IN ({0}))'.format(
                _inherited_server_ids_sql(
                    model, attribute_conditions, related_via_attribute
                )
            )
        path_conditions.append((condition, servertype_ids))

    if len(path_conditions) == 1:
        return path_conditions[0][0]

    # The paths are OR'ed together outside their subqueries, rather than
    # inside a single EXISTS: Postgres cannot make a semi join out of an
    # EXISTS whose correlation to "server" is an OR of alternatives, and
    # falls back to a nested loop over every (server, sub) pair.
    #
    # The servertype guard comes first in each branch on purpose.  Postgres
    # reorders AND clauses by cost at the top level only, not inside the
    # branches of an OR, and otherwise evaluates left to right; the cheap
    # test first lets it skip the subquery probe for servertypes that do
    # not use that path at all.
    return '({0})'.format(' OR '.join(
        '(server.servertype_id IN ({0}) AND {1})'.format(
            ', '.join("'{0}'".format(s) for s in servertype_ids), condition
        )
        for condition, servertype_ids in path_conditions
    ))


def _exists_sql(model, alias, conditions):
    return 'EXISTS (SELECT 1 FROM {0} AS {1} WHERE {2})'.format(
        model._meta.db_table, alias, ' AND '.join(c for c in conditions if c)
    )


def _inherited_server_ids_sql(
    model, attribute_conditions, related_via_attribute
):
    """SELECT the ids of servers inheriting a matching value via an attribute

    Nothing in the returned subquery references the outer "server".  That is
    the point: as a correlated EXISTS, an inherited path was re-evaluated
    once per candidate server, re-finding the same matching rows every time
    and then testing each (server, match) pair one by one - for a supernet
    path that meant millions of inet containment checks, none of them able
    to use the GiST index on server_inet_attribute.value because the plan
    probed the server's address by key and only then filtered on
    containment.  Uncorrelated, Postgres evaluates it once, hashes the ids,
    and probes the hash per row; the containment join is driven from the
    matching networks' prefixes, which is what the index is for.  The cost
    becomes (candidates + matches) instead of their product.

    The selected column is a NOT NULL foreign key in every branch, so the
    caller's "server.server_id IN (...)" keeps plain set semantics under NOT
    as well: no NULL can leak into the result and turn the test unknown.
    """
    sub_table = model._meta.db_table
    rel_table = ServerRelationAttribute._meta.db_table
    conditions = list(attribute_conditions)

    if related_via_attribute.type == 'relation':
        # The server points at the owner of the value.
        select = 'rel1.server_id'
        from_ = '{0} AS rel1'.format(rel_table)
        joins = [
            'JOIN {0} AS sub ON (sub.server_id = rel1.value)'.format(sub_table)
        ]
        conditions.insert(0, "rel1.attribute_id = '{0}'".format(
            related_via_attribute.attribute_id
        ))
    elif related_via_attribute.type == 'reverse':
        # The owner of the value points at the server.
        select = 'rel1.value'
        from_ = '{0} AS rel1'.format(rel_table)
        joins = [
            'JOIN {0} AS sub ON (sub.server_id = rel1.server_id)'
            .format(sub_table)
        ]
        conditions.insert(0, "rel1.attribute_id = '{0}'".format(
            related_via_attribute.reversed_attribute_id
        ))
    else:
        assert related_via_attribute.type == 'supernet'
        # The owner of the value is a network containing one of the
        # server's addresses on the same inet attribute.  Same join graph
        # as _supernet_exists_sql(), minus the correlation to "server".
        af_join, af_where = _supernet_af_sql(related_via_attribute)
        select = 'server_addr.server_id'
        from_ = '{0} AS sub'.format(sub_table)
        joins = [
            'JOIN {0} AS supernet ON (supernet.server_id = sub.server_id)'
            .format(Server._meta.db_table),
            'JOIN {0} AS net_addr ON (net_addr.server_id = supernet.server_id)'
            .format(ServerInetAttribute._meta.db_table),
            'JOIN {0} AS server_addr ON ('
            'server_addr.attribute_id = net_addr.attribute_id'
            ' AND net_addr.value >>= server_addr.value)'
            .format(ServerInetAttribute._meta.db_table),
        ] + [
            f'JOIN {x[0]} AS {x[1]} ON ({" AND ".join(x[2])})' for x in af_join
        ]
        conditions.insert(
            0, _target_servertype_sql('supernet', related_via_attribute)
        )
        conditions.extend(af_where)

    return 'SELECT {0} FROM {1} {2} WHERE {3}'.format(
        select, from_, ' '.join(joins),
        ' AND '.join(c for c in conditions if c),
    )


def _supernet_af_sql(attribute):
    """Joins and conditions pinning a supernet match to one address family"""
    if not attribute.inet_address_family:
        return (), ()
    af_join = (
        (Attribute._meta.db_table, 'server_attr', ('server_attr.attribute_id = server_addr.attribute_id',)),
        (Attribute._meta.db_table, 'net_attr', ('net_attr.attribute_id = net_addr.attribute_id',)),
    )
    af_where = (
        f"net_attr.inet_address_family = '{attribute.inet_address_family}'",
        f"server_attr.inet_address_family = '{attribute.inet_address_family}'",
    )
    return af_join, af_where


def _supernet_exists_sql(attribute: Attribute, supernet_alias: str, addr_match: str, where: tuple[str, ...]):
    af_join, af_where = _supernet_af_sql(attribute)

    joins = (
        (ServerInetAttribute._meta.db_table, 'server_addr', ('server_addr.server_id = server.server_id',)),
        (ServerInetAttribute._meta.db_table, 'net_addr', (
            'net_addr.value ' + addr_match,
            'net_addr.attribute_id = server_addr.attribute_id',
            f'net_addr.server_id = {supernet_alias}.server_id',
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
