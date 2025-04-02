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
        if type(filt) == Any and type(value) == BaseFilter:
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
            template = (
                "{{0}} << {0} AND NOT EXISTS ("
                '   SELECT 1 '
                '   FROM server AS supernet '
                '   WHERE {{0}} << supernet.intern_ip AND '
                '       supernet.intern_ip << {0}'
                ')'
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


def _condition_sql(attribute, template, related_vias):
    if attribute.special:
        return template.format('server.' + attribute.special.field)

    if attribute.type == 'supernet':
        if attribute.inet_address_family:
            af_join = (
                (Attribute._meta.db_table, 'server_attr', ('server_attr.attribute_id = server_addr.attribute_id',)),
                (Attribute._meta.db_table, 'net_attr', ('net_attr.attribute_id = net_addr.attribute_id',)),
            )
            af_where = (
                f"net_attr.inet_address_family = '{attribute.inet_address_family}'",
                f"server_attr.inet_address_family = '{attribute.inet_address_family}'",
            )
        else:
            af_join = ()
            af_where = ()

        return _exists_sql_join(Server, 'net',
            (
                (ServerInetAttribute._meta.db_table, 'server_addr', ('server_addr.server_id = server.server_id',)),
                (ServerInetAttribute._meta.db_table, 'net_addr', (
                    'net_addr.value >>= server_addr.value',
                    'net_addr.attribute_id = server_addr.attribute_id',
                    'net_addr.server_id = net.server_id',
                )),
            ) + af_join,
            (
                f"net.servertype_id = '{attribute.target_servertype_id}'",
                template.format('net.server_id'),
            ) + af_where,
        )

    if attribute.type == 'domain':
        return _exists_sql(Server, 'sub', (
            "sub.servertype_id = '{0}'".format(attribute.target_servertype_id),
            "server.hostname ~ ('\\A[^\.]+\.' || regexp_replace("
            "sub.hostname, '(\*|\-|\.)', '\\\1', 'g') || '\\Z')",
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

    # We start with the condition for the attributes the server has on
    # its own.  Then, add the conditions for all possible relations.  They
    # are going to be OR'ed together.
    relation_conditions = []
    for related_via_attribute, servertype_ids in related_vias.items():
        if related_via_attribute is None:
            # The condition for directly attached attributes
            relation_condition = 'server.server_id = sub.server_id'
        elif related_via_attribute.type == 'supernet':
            if related_via_attribute.inet_address_family:
                af_join = (
                    (Attribute._meta.db_table, 'server_attr', ('server_attr.attribute_id = server_addr.attribute_id',)),
                    (Attribute._meta.db_table, 'net_attr', ('net_attr.attribute_id = net_addr.attribute_id',)),
                )
                af_where = (
                    f"net_attr.inet_address_family = '{related_via_attribute.inet_address_family}'",
                    f"server_attr.inet_address_family = '{related_via_attribute.inet_address_family}'",
                )
            else:
                af_join = ()
                af_where = ()

            relation_condition = _exists_sql_join(Server, 'rel1',
                (
                    (ServerInetAttribute._meta.db_table, 'server_addr', ('server_addr.server_id = server.server_id',)),
                    (ServerInetAttribute._meta.db_table, 'net_addr', (
                        'net_addr.value >>= server_addr.value',
                        'net_addr.attribute_id = server_addr.attribute_id',
                        'net_addr.server_id = rel1.server_id',
                    )),
                ) + af_join,
                (
                    f"rel1.servertype_id = '{related_via_attribute.target_servertype_id}'",
                    'rel1.server_id = sub.server_id'
                ) + af_where,
            )
        elif related_via_attribute.type == 'reverse':
            relation_condition = _exists_sql(ServerRelationAttribute, 'rel1', (
                "rel1.attribute_id = '{0}'".format(
                    related_via_attribute.reversed_attribute_id
                ),
                'rel1.value = server.server_id',
                'rel1.server_id = sub.server_id',
            ))
        else:
            assert related_via_attribute.type == 'relation'
            relation_condition = _exists_sql(ServerRelationAttribute, 'rel1', (
                "rel1.attribute_id = '{0}'"
                .format(related_via_attribute.attribute_id),
                'rel1.server_id = server.server_id',
                'rel1.value = sub.server_id',
            ))
        relation_conditions.append((relation_condition, servertype_ids))

    if len(relation_conditions) == 1:
        mixed_relation_condition = relation_conditions[0][0]
    else:
        mixed_relation_condition = '({0})'.format(' OR '.join(
            '({0} AND server.servertype_id IN ({1}))'
            .format(relation_condition, ', '.join(
                "'{0}'".format(s) for s in servertype_ids)
            )
            for relation_condition, servertype_ids in relation_conditions
        ))

    return _exists_sql(model, 'sub', (
        mixed_relation_condition,
        "sub.attribute_id = '{0}'".format(attribute.attribute_id),
        template.format('sub.value'),
    ))


def _exists_sql(model, alias, conditions):
    return 'EXISTS (SELECT 1 FROM {0} AS {1} WHERE {2})'.format(
        model._meta.db_table, alias, ' AND '.join(c for c in conditions if c)
    )


def _exists_sql_join(model, alias, joins, conditions):
    return 'EXISTS (SELECT 1 FROM {0} AS {1} {2} WHERE {3})'.format(
        model._meta.db_table,
        alias,
        ' '.join(f'JOIN {x[0]} AS {x[1]} ON ({" AND ".join(x[2])})' for x in joins),
        ' AND '.join(c for c in conditions)
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
