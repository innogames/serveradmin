"""Serveradmin - SQL Generator

Copyright (c) 2018 InnoGames GmbH
"""
# XXX: It is terrible to generate SQL this way.  We should make this use
# parameterized queries at least.
# XXX: The code in this module is almost randomly split into functions.  Do
# not try to guess what they would do.

from adminapi.filters import (
    All,
    Any,
    BaseFilter,
    Comparison,
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
    ServerRelationAttribute,
)


# The "possible_servertypes_id" argument is carried all the way through
# most of the functions to optimize related_via_attribute selection.
# TODO: Find a nicer way to achieve this
def get_server_query(attribute_filters, possible_servertype_ids=None):
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
            _get_sql_condition(a, f, possible_servertype_ids)
            for a, f in attribute_filters
        )
    sql += ' ORDER BY server.hostname'

    return sql


def _get_sql_condition(attribute, filt, possible_servertype_ids=None):
    assert isinstance(filt, BaseFilter)

    if isinstance(filt, (Not, Any)):
        return _logical_filter_sql_condition(
            attribute, filt, possible_servertype_ids
        )

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

        # TODO: Better return errors for mismatching datatypes than casting
        negate = not filt.value or filt.value == 'false'
    elif isinstance(filt, Regexp):
        template = '{0}::text ~ E' + _raw_sql_escape(filt.value)
    elif isinstance(filt, (
        Comparison,
        GreaterThanOrEquals,
        LessThanOrEquals,
    )):
        template = _basic_comparison_filter_template(attribute, filt)
    elif isinstance(filt, Overlaps):
        template = _containment_filter_template(attribute, filt)
    elif isinstance(filt, Empty):
        negate = True
        template = '{0} IS NOT NULL'
    else:
        template = '{0} = ' + _raw_sql_escape(filt.value)

    return _covered_sql_condition(
        attribute, template, negate, possible_servertype_ids
    )


def _covered_sql_condition(
    attribute, template, negate=False, possible_servertype_ids=None
):
    if attribute.type in ['relation', 'reverse', 'supernet']:
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
        _condition_sql(attribute, template, possible_servertype_ids)
    )


def _logical_filter_sql_condition(
    attribute, filt, possible_servertype_ids=None
):
    if isinstance(filt, Not):
        return 'NOT ({0})'.format(_get_sql_condition(
            attribute, filt.value, possible_servertype_ids
        ))

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
            templates.append(_get_sql_condition(
                attribute, value, possible_servertype_ids
            ))

    if simple_values:
        if len(simple_values) == 1:
            template = _get_sql_condition(
                attribute, simple_values[0], possible_servertype_ids
            )
        else:
            template = _covered_sql_condition(
                attribute,
                '{{0}} IN ({0})'.format(', '.join(
                    _raw_sql_escape(v.value) for v in simple_values
                )),
                False,
                possible_servertype_ids,
            )
        templates.append(template)

    return '({0})'.format(joiner.join(templates))


def _basic_comparison_filter_template(attribute, filt):
    if isinstance(filt, Comparison):
        operator = filt.comparator
    elif isinstance(filt, GreaterThan):
        operator = '>'
    elif isinstance(filt, GreaterThanOrEquals):
        operator = '>='
    elif isinstance(filt, LessThan):
        operator = '<'
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


def _condition_sql(attribute, template, possible_servertype_ids=None):
    if attribute.special:
        return template.format('server.' + attribute.special.field)

    if attribute.type == 'supernet':
        return _exists_sql(Server, 'sub', (
            "sub.servertype_id = '{0}'".format(attribute.target_servertype_id),
            'sub.intern_ip >>= server.intern_ip',
            template.format('sub.server_id'),
        ))

    if attribute.type == 'reverse':
        return _exists_sql(ServerRelationAttribute, 'sub', (
            "sub.attribute_id = '{0}'".format(attribute.reversed_attribute_id),
            'sub.value = server.server_id',
            template.format('sub.server_id'),
        ))

    return _real_condition_sql(attribute, template, possible_servertype_ids)


def _real_condition_sql(attribute, template, possible_servertype_ids=None):
    model = ServerAttribute.get_model(attribute.type)
    assert model is not None

    # We start with the condition for the attributes the server has on
    # its own.  Then, add the conditions for all possible relations.  They
    # are going to be OR'ed together.
    relation_conditions = []
    related_via_attributes = set()
    other_servertype_ids = list()
    queryset = attribute.servertype_attributes  # TODO: Stop making queries
    if possible_servertype_ids:
        queryset = queryset.filter(servertype_id__in=possible_servertype_ids)
    for sa in queryset:
        if sa.related_via_attribute:
            related_via_attributes.add(sa.related_via_attribute)
        else:
            other_servertype_ids.append(sa.servertype_id)
    for related_via_attribute in related_via_attributes:
        queryset = related_via_attribute.servertype_attributes
        if possible_servertype_ids:
            queryset = queryset.filter(
                servertype_id__in=possible_servertype_ids
            )
        related_via_servertype_ids = [sa.servertype_id for sa in queryset]
        assert related_via_servertype_ids
        if related_via_attribute.type == 'supernet':
            relation_condition = _exists_sql(Server, 'rel1', (
                "rel1.servertype_id = '{0}'".format(
                    related_via_attribute.target_servertype_id
                ),
                'rel1.intern_ip >>= server.intern_ip',
                'rel1.server_id = sub.server_id',
            ))
        elif related_via_attribute.type == 'reverse':
            relation_condition = _exists_sql(ServerRelationAttribute, 'rel1', (
                "rel1.attribute_id = '{0}'".format(
                    related_via_attribute.reversed_attribute.attribute_id
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
        relation_conditions.append(
            (relation_condition, related_via_servertype_ids)
        )
    if other_servertype_ids:
        relation_conditions.append(
            ('server.server_id = sub.server_id', other_servertype_ids)
        )
    assert relation_conditions

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
