from __future__ import unicode_literals

from decimal import Decimal

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
from serveradmin.serverdb.models import Server, ServerAttribute


class QueryBuilder(object):
    def __init__(self, servertypes, filters):
        self.servertypes = servertypes
        self.filters = filters

    def build_sql(self):
        sql = (
            'SELECT'
            ' server.server_id,'
            ' server.hostname,'
            ' server.intern_ip,'
            ' server.servertype_id AS _servertype_id,'
            ' server.project_id AS _project_id'
            ' FROM server'
            ' WHERE servertype_id IN ({})'
            .format(', '.join('\'{}\''.format(s.pk) for s in self.servertypes))
        )
        for attribute, value in self.filters.items():
            sql += ' AND ' + self.get_sql_condition(attribute, value)

        return sql

    def get_sql_condition(self, attribute, filt):
        assert isinstance(filt, BaseFilter)

        if isinstance(filt, (Not, Any)):
            return self._logical_filter_sql_condition(attribute, filt)

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

            # TODO Better return errors for mismatching datatypes than casting
            negate = not filt.value or filt.value == 'false'

        elif isinstance(filt, Regexp):
            value = self._raw_sql_escape(filt.value)
            if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
                template = (
                    '{{0}} IN ('
                    '   SELECT server_id'
                    '   FROM server'
                    '   WHERE hostname ~ E{0}'
                    ')'
                    .format(value)
                )
            else:
                template = '{{0}}::text ~ E{0}'.format(value)

        elif isinstance(filt, (
            Comparison,
            GreaterThanOrEquals,
            LessThanOrEquals,
        )):
            template = self._basic_comparison_filter_template(attribute, filt)

        elif isinstance(filt, Overlaps):
            template = self._containment_filter_template(attribute, filt)

        elif isinstance(filt, Empty):
            negate = True
            template = '{0} IS NOT NULL'

        else:
            template = '{0} = ' + self._value_to_sql(attribute, filt.value)

        return (
            ('NOT ' if negate else '') +
            self._condition_sql(attribute, template)
        )

    def _logical_filter_sql_condition(self, attribute, filt):
        if isinstance(filt, Not):
            return 'NOT ({0})'.format(self.get_sql_condition(
                attribute, filt.value
            ))

        if isinstance(filt, All):
            joiner = ' AND '
        else:
            joiner = ' OR '

        if not filt.values:
            return 'NOT ({0})'.format(joiner.join(['true', 'false']))

        return '({0})'.format(joiner.join(
            self.get_sql_condition(attribute, v) for v in filt.values
        ))

    def _basic_comparison_filter_template(self, attribute, filt):
        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            raise FilterValueError(
                'Cannot compare hostname attribute "{}"'.format(attribute)
            )

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
            operator, self._value_to_sql(attribute, filt.value)
        )

    def _containment_filter_template(self, attribute, filt):
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

        return template.format(self._value_to_sql(attribute, value))

    def _value_to_sql(self, attribute, value):
        # Validations of special relation attributes
        if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
            try:
                return str(Server.objects.get(hostname=value).server_id)
            except Server.DoesNotExist as error:
                raise FilterValueError(str(error))

        # TODO Better return errors for mismatching datatypes than casting
        if attribute.type == 'number':
            return str(Decimal(value))

        return self._raw_sql_escape(value)

    def _condition_sql(self, attribute, template):  # NOQA C901
        if attribute.special:
            field = attribute.special.field
            if field.startswith('_'):
                field = field[1:]

            return template.format('server.' + field)

        if attribute.type == 'supernet':
            return self._exists_sql('server', 'sub', (
                "sub.servertype_id = '{0}'".format(
                    attribute.target_servertype.pk
                ),
                'sub.intern_ip >>= server.intern_ip',
                template.format('sub.server_id'),
            ))

        rel_table = ServerAttribute.get_model('hostname')._meta.db_table

        if attribute.type == 'reverse_hostname':
            return self._exists_sql(rel_table, 'sub', (
                "sub.attribute_id = '{0}'".format(
                    attribute.reversed_attribute.pk
                ),
                'sub.value = server.server_id',
                template.format('sub.server_id'),
            ))

        # We must have handled the virtual attribute types.
        assert attribute.can_be_materialized()

        # We start with the condition for the attributes the server has on
        # its own.  Then, add the conditions for all possible relations.  They
        # are going to be OR'ed together.
        relation_conditions = []
        related_via_attributes = set()
        other_servertypes = list()
        for sa in attribute.servertype_attributes.filter(
            _servertype__in=self.servertypes
        ):
            if sa.related_via_attribute:
                related_via_attributes.add(sa.related_via_attribute)
            else:
                other_servertypes.append(sa.servertype)
        for related_via_attribute in related_via_attributes:
            related_via_servertypes = tuple(
                sa.servertype
                for sa in related_via_attribute.servertype_attributes.filter(
                    _servertype__in=self.servertypes
                )
            )
            assert related_via_servertypes
            if related_via_attribute.type == 'supernet':
                relation_condition = self._exists_sql('server', 'rel1', (
                    "rel1.servertype_id = '{0}'".format(
                        related_via_attribute.target_servertype.pk
                    ),
                    'rel1.intern_ip >>= server.intern_ip',
                    'rel1.server_id = sub.server_id',
                ))
            elif related_via_attribute.type == 'reverse_hostname':
                relation_condition = self._exists_sql(rel_table, 'rel1', (
                    "rel1.attribute_id = '{0}'".format(
                        related_via_attribute.reversed_attribute.pk
                    ),
                    'rel1.value = server.server_id',
                    'rel1.server_id = sub.server_id',
                ))
            else:
                assert related_via_attribute.type == 'hostname'
                relation_condition = self._exists_sql(rel_table, 'rel1', (
                    "rel1.attribute_id = '{0}'".format(
                        related_via_attribute.pk
                    ),
                    'rel1.server_id = server.server_id',
                    'rel1.value = sub.server_id',
                ))
            relation_conditions.append(
                (relation_condition, related_via_servertypes)
            )
        if other_servertypes:
            relation_conditions.append(
                ('server.server_id = sub.server_id', other_servertypes)
            )
        assert relation_conditions

        table = ServerAttribute.get_model(attribute.type)._meta.db_table
        if len(relation_conditions) == 1:
            mixed_relation_condition = relation_conditions[0][0]
        else:
            mixed_relation_condition = '({0})'.format(' OR '.join(
                '({0} AND server.servertype_id IN ({1}))'
                .format(relation_condition, ', '.join(
                    "'{0}'".format(s.pk) for s in servertypes)
                )
                for relation_condition, servertypes in relation_conditions
            ))

        return self._exists_sql(table, 'sub', (
            mixed_relation_condition,
            "sub.attribute_id = '{0}'".format(attribute.pk),
            template.format('sub.value'),
        ))

    def _exists_sql(self, table, alias, conditions):
        return 'EXISTS (SELECT 1 FROM {0} AS {1} WHERE {2})'.format(
            table, alias, ' AND '.join(c for c in conditions if c)
        )

    def _raw_sql_escape(self, value):
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
