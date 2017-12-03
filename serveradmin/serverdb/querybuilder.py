from __future__ import unicode_literals

from decimal import Decimal

from adminapi.filters import (
    And,
    Any,
    BaseFilter,
    Comparison,
    Contains,
    ContainedBy,
    ContainedOnlyBy,
    Empty,
    ExactMatch,
    FilterValueError,
    Or,
    Overlaps,
    Regexp,
    StartsWith,
    Not,
)
from serveradmin.serverdb.models import Attribute, Server, ServerAttribute


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
        )
        sql += ' WHERE ' + self.get_sql_condition(
            Attribute.objects.get(pk='servertype'),
            Any(*(s.pk for s in self.servertypes)),
        )
        for attribute, value in self.filters.items():
            sql += ' AND ' + self.get_sql_condition(attribute, value)

        return sql

    def get_sql_condition(self, attribute, filt):  # NOQA C901

        if isinstance(filt, (Not, Or)):
            return self._logical_filter_sql_condition(attribute, filt)

        negate = False
        template = ''

        if attribute.type == 'boolean':
            if isinstance(filt, BaseFilter):
                raise FilterValueError(
                    'Boolean attribute "{}" cannot be used with {}() filter'
                    .format(attribute, type(filt).__name__)
                )

            negate = not filt or filt == 'false'

        elif isinstance(filt, Regexp):
            value = self._raw_sql_escape(filt.value)
            if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
                template = (
                    '{{0}} IN ('
                    '   SELECT server_id'
                    '   FROM server'
                    '   WHERE hostname ~ E{}'
                    ')'
                    .format(value)
                )
            else:
                template = '{{}}::text ~ E{}'.format(value)

        elif isinstance(filt, Comparison):
            if attribute.type in ('hostname', 'reverse_hostname', 'supernet'):
                raise FilterValueError(
                    'Cannot compare hostnames attribute "{}"'.format(attribute)
                )

            template = '{{}} {} {}'.format(
                filt.comparator,
                self._value_to_sql(attribute, filt.value),
            )

        elif isinstance(filt, Any):
            # TODO Use arrays of Psycopg2
            if filt.values:
                template = '{{}} = ANY (ARRAY[{}])'.format(', '.join(
                    self._value_to_sql(attribute, v) for v in filt.values
                ))

        elif isinstance(filt, Overlaps):
            template = self._containment_filter_template(attribute, filt)

        elif isinstance(filt, Empty):
            negate = True
            template = '{} IS NOT NULL'

        elif isinstance(filt, ExactMatch):
            template = '{} = ' + self._value_to_sql(attribute, filt.value)

        else:
            template = '{} = ' + self._value_to_sql(attribute, filt)

        return (
            ('NOT ' if negate else '') +
            self._condition_sql(attribute, template)
        )

    def _logical_filter_sql_condition(self, attribute, filt):
        if isinstance(filt, Not):
            return 'NOT ({0})'.format(self.get_sql_condition(
                attribute, filt.value
            ))

        if isinstance(filt, And):
            joiner = ' AND '
        else:
            joiner = ' OR '

        if not filt.filters:
            return 'NOT ({0})'.format(joiner.join(['true', 'false']))

        return '({0})'.format(joiner.join(
            self.get_sql_condition(attribute, f) for f in filt.filters
        ))

    def _containment_filter_template(self, attribute, filt):
        template = None     # To be formatted 2 times
        value = filt.value

        if attribute.type == 'inet':
            if isinstance(filt, StartsWith):
                template = "{{}} >>= {} AND host({{}}) = host({})"
            elif isinstance(filt, Contains):
                template = "{{}} >>= {}"
            elif isinstance(filt, ContainedOnlyBy):
                template = (
                    "{{}} << {} AND NOT EXISTS ("
                    '   SELECT 1 '
                    '   FROM server AS supernet '
                    '   WHERE {{}} << supernet.intern_ip AND '
                    '       supernet.intern_ip << {}'
                    ')'
                )
            elif isinstance(filt, ContainedBy):
                template = "{{}} <<= {}"
            else:
                template = "{{}} && {}"

        elif attribute.type == 'string':
            if isinstance(filt, Contains):
                template = "{{}} LIKE {}"
                value = '{}{}{}'.format(
                    '' if isinstance(filt, StartsWith) else '%', value, '%'
                )
            elif isinstance(filt, ContainedBy):
                template = "{} LIKE '%%' || {{}} || '%%'"

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

        if attribute.type == 'number':
            return str(Decimal(value))

        # Those needs to be quoted, because they are stored as string on
        # the database.
        if attribute.type == 'boolean':
            return self._raw_sql_escape(1 if value else 0)
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
