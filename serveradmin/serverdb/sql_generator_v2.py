"""Serveradmin - SQL Generator V2 (Django ORM)

Copyright (c) 2024 InnoGames GmbH

This module provides server query generation using Django ORM instead of
raw SQL string concatenation. It provides the same interface as sql_generator.py
for compatibility but returns a QuerySet instead of a SQL string.

Benefits over v1:
- Parameterized queries (SQL injection protection)
- Django's query optimization and lazy evaluation
- Better maintainability and testability
- Type safety through Django's ORM
"""

from django.db.models import Q, Exists, OuterRef, Subquery, F
from django.db.models.expressions import RawSQL

from adminapi.filters import (
    All,
    Any,
    BaseFilter,
    Contains,
    ContainedBy,
    ContainedOnlyBy,
    Empty,
    GreaterThan,
    GreaterThanOrEquals,
    LessThan,
    LessThanOrEquals,
    Overlaps,
    Regexp,
    StartsWith,
    Not,
    FilterValueError,
)
from serveradmin.serverdb.models import (
    Attribute,
    Server,
    ServerAttribute,
    ServerBooleanAttribute,
    ServerInetAttribute,
    ServerRelationAttribute,
)


def get_server_query(attribute_filters, related_vias):
    """
    Build a Django QuerySet for filtering servers.

    This function provides the same interface as sql_generator.get_server_query()
    but returns a QuerySet instead of a raw SQL string.

    Args:
        attribute_filters: List of (Attribute, Filter) tuples to apply
        related_vias: Dict mapping attribute_id to {related_via_attr: [servertype_ids]}

    Returns:
        QuerySet[Server]: Filtered and ordered queryset of servers
    """
    queryset = Server.objects.all()

    for attribute, filt in attribute_filters:
        condition = _build_attribute_condition(attribute, filt, related_vias)
        queryset = queryset.filter(condition)

    return queryset.order_by('hostname')


def _build_attribute_condition(attribute, filt, related_vias):
    """
    Build a Q object for filtering by an attribute with a given filter.

    Args:
        attribute: The Attribute model instance
        filt: The filter to apply (BaseFilter subclass)
        related_vias: Dict of related_via configurations

    Returns:
        Q: Django Q object representing the filter condition
    """
    # Handle logical filters (Not, Any, All) first
    if isinstance(filt, Not):
        inner_condition = _build_attribute_condition(
            attribute, filt.value, related_vias
        )
        return ~inner_condition

    if isinstance(filt, (Any, All)):
        return _build_logical_condition(attribute, filt, related_vias)

    # Build the value condition based on filter type
    value_condition = _build_value_condition(attribute, filt)

    # Wrap in attribute lookup (special, standard, or complex type)
    return _build_attribute_lookup(attribute, value_condition, related_vias)


def _build_logical_condition(attribute, filt, related_vias):
    """
    Build Q object for Any (OR) or All (AND) logical filters.

    Args:
        attribute: The Attribute model instance
        filt: Any or All filter instance
        related_vias: Dict of related_via configurations

    Returns:
        Q: Combined Q object with OR/AND logic
    """
    if not filt.values:
        # Empty Any() always fails, empty All() always passes
        if isinstance(filt, All):
            return Q()  # Empty Q matches everything
        else:
            return Q(pk__isnull=True) & Q(pk__isnull=False)  # Always False

    # Optimization: collect simple BaseFilter values for IN clause
    simple_values = []
    complex_conditions = []

    for value in filt.values:
        if isinstance(filt, Any) and type(value) == BaseFilter:
            simple_values.append(value.value)
        else:
            complex_conditions.append(
                _build_attribute_condition(attribute, value, related_vias)
            )

    # Build optimized IN clause for simple values
    if simple_values:
        if len(simple_values) == 1:
            in_condition = _build_attribute_condition(
                attribute, BaseFilter(simple_values[0]), related_vias
            )
        else:
            in_condition = _build_in_condition(attribute, simple_values, related_vias)
        complex_conditions.append(in_condition)

    # Combine with OR (Any) or AND (All)
    if isinstance(filt, All):
        result = Q()
        for condition in complex_conditions:
            result &= condition
    else:
        # Build OR without starting with FALSE to avoid inefficient
        # "(pk IS NULL AND pk IS NOT NULL) OR ..." SQL pattern
        result = None
        for condition in complex_conditions:
            if result is None:
                result = condition
            else:
                result |= condition
        # If no conditions, return always-false condition
        if result is None:
            result = Q(pk__isnull=True) & Q(pk__isnull=False)

    return result


def _build_in_condition(attribute, values, related_vias):
    """
    Build an optimized IN condition for multiple simple values.

    Args:
        attribute: The Attribute model instance
        values: List of values to match
        related_vias: Dict of related_via configurations

    Returns:
        Q: Q object with IN clause
    """
    if attribute.special:
        field = _get_special_field(attribute)
        return Q(**{f'{field}__in': values})

    # For regular attributes, use EXISTS with IN
    return _build_attribute_lookup(
        attribute,
        Q(value__in=values),
        related_vias,
    )


def _build_value_condition(attribute, filt):
    """
    Build the value comparison Q object based on filter type.

    Args:
        attribute: The Attribute model instance
        filt: The filter to apply

    Returns:
        Q: Q object for the value comparison (to be used in subquery)
    """
    # Boolean attributes: presence check only
    if attribute.type == 'boolean':
        if type(filt) != BaseFilter:
            raise FilterValueError(
                f'Boolean attribute "{attribute}" cannot be used with '
                f'{type(filt).__name__}() filter'
            )
        # For booleans, the filter value determines EXISTS vs NOT EXISTS
        # Return a marker that _build_attribute_lookup will handle
        return Q(_boolean_negate=not filt.value)

    # Regexp filter
    if isinstance(filt, Regexp):
        return Q(value__regex=filt.value)

    # Comparison filters
    if isinstance(filt, GreaterThan):
        return Q(value__gt=filt.value)
    if isinstance(filt, GreaterThanOrEquals):
        return Q(value__gte=filt.value)
    if isinstance(filt, LessThan):
        return Q(value__lt=filt.value)
    if isinstance(filt, LessThanOrEquals):
        return Q(value__lte=filt.value)

    # Containment filters (inet and string)
    if isinstance(filt, Overlaps):
        return _build_containment_condition(attribute, filt)

    # Empty filter
    if isinstance(filt, Empty):
        # Empty means attribute doesn't exist - handled by NOT EXISTS
        return Q(_empty_filter=True)

    # Default: equality
    return Q(value=filt.value)


def _build_containment_condition(attribute, filt):
    """
    Build containment condition for inet or string attributes.

    Args:
        attribute: The Attribute model instance
        filt: Containment filter (Contains, ContainedBy, Overlaps, etc.)

    Returns:
        Q: Q object with appropriate containment check
    """
    if attribute.type == 'inet':
        return _build_inet_containment(filt)
    elif attribute.type == 'string':
        return _build_string_containment(filt)
    else:
        raise FilterValueError(
            f'Cannot use {type(filt).__name__} filter on "{attribute}"'
        )


def _build_inet_containment(filt):
    """
    Build inet containment condition using PostgreSQL operators.

    Args:
        filt: Containment filter instance

    Returns:
        Q: Q object with RawSQL for inet operators
    """
    value = str(filt.value)

    if isinstance(filt, StartsWith):
        # >>= contains and host() matches
        return Q(
            value__contained_by_or_equal=value,
            _inet_host_match=value,
        )
    elif isinstance(filt, Contains):
        # >>= (contains or equals)
        return Q(_inet_contains=value)
    elif isinstance(filt, ContainedOnlyBy):
        # << (strictly contained) with no intermediate supernet
        # This is complex - needs subquery for supernet check
        return Q(_inet_contained_only_by=value)
    elif isinstance(filt, ContainedBy):
        # <<= (contained by or equals)
        return Q(_inet_contained_by=value)
    else:
        # && (overlaps)
        return Q(_inet_overlaps=value)


def _build_string_containment(filt):
    """
    Build string containment condition using LIKE.

    Args:
        filt: Containment filter instance

    Returns:
        Q: Q object with contains/startswith lookup
    """
    if isinstance(filt, StartsWith):
        return Q(value__startswith=filt.value)
    elif isinstance(filt, Contains):
        return Q(value__contains=filt.value)
    elif isinstance(filt, ContainedBy):
        # Reverse: check if value is contained in filter value
        return Q(_string_contained_by=filt.value)
    else:
        raise FilterValueError(
            f'Cannot use {type(filt).__name__} filter on string attribute'
        )


def _build_attribute_lookup(attribute, value_condition, related_vias):
    """
    Build the full attribute lookup with appropriate subquery structure.

    Args:
        attribute: The Attribute model instance
        value_condition: Q object for value comparison
        related_vias: Dict of related_via configurations

    Returns:
        Q: Complete Q object with EXISTS subquery if needed
    """
    # Special attributes: direct field lookup on Server
    if attribute.special:
        return _build_special_lookup(attribute, value_condition)

    # Complex attribute types with special handling
    if attribute.type == 'supernet':
        return _build_supernet_lookup(attribute, value_condition)

    if attribute.type == 'domain':
        return _build_domain_lookup(attribute, value_condition)

    if attribute.type == 'reverse':
        return _build_reverse_lookup(attribute, value_condition)

    # Standard attributes: use related_vias for lookup
    return _build_standard_lookup(attribute, value_condition, related_vias)


def _get_special_field(attribute):
    """Get the Server model field for a special attribute."""
    field_map = {
        'object_id': 'server_id',
        'hostname': 'hostname',
        'servertype': 'servertype_id',
        'intern_ip': 'intern_ip',
    }
    return field_map.get(attribute.attribute_id, attribute.special.field)


def _build_special_lookup(attribute, value_condition):
    """
    Build lookup for special attributes (hostname, servertype, etc.).

    Args:
        attribute: Special attribute instance
        value_condition: Q object with value comparison

    Returns:
        Q: Q object with direct field lookup
    """
    field = _get_special_field(attribute)

    # Handle special markers in value_condition
    if hasattr(value_condition, 'children'):
        for child in value_condition.children:
            if isinstance(child, tuple):
                key, val = child
                if key == '_boolean_negate':
                    # Boolean on special field
                    return ~Q(**{f'{field}__isnull': False}) if val else Q(**{f'{field}__isnull': False})
                if key == '_empty_filter':
                    return ~Q(**{f'{field}__isnull': False})

    # Transform value__X to field__X
    transformed = Q()
    for child in value_condition.children if hasattr(value_condition, 'children') else []:
        if isinstance(child, tuple):
            key, val = child
            if key.startswith('value'):
                new_key = key.replace('value', field, 1)
                transformed.children.append((new_key, val))
            else:
                transformed.children.append(child)
        else:
            transformed.children.append(child)

    transformed.connector = value_condition.connector
    transformed.negated = value_condition.negated

    # Handle relation types: wrap hostname lookup in subquery
    if attribute.type in ['relation', 'reverse', 'supernet', 'domain']:
        return Exists(
            Server.objects.filter(
                pk=OuterRef(field),
            ).filter(_transform_to_hostname(transformed))
        )

    return transformed if transformed.children else value_condition


def _transform_to_hostname(q_obj):
    """Transform value lookups to hostname lookups for relation attributes."""
    if not hasattr(q_obj, 'children'):
        return q_obj

    transformed = Q()
    for child in q_obj.children:
        if isinstance(child, tuple):
            key, val = child
            if key.startswith('value'):
                new_key = key.replace('value', 'hostname', 1)
                transformed.children.append((new_key, val))
            else:
                transformed.children.append(child)
        elif isinstance(child, Q):
            transformed.children.append(_transform_to_hostname(child))
        else:
            transformed.children.append(child)

    transformed.connector = q_obj.connector
    transformed.negated = q_obj.negated
    return transformed


def _build_standard_lookup(attribute, value_condition, related_vias):
    """
    Build lookup for standard attributes using EXISTS subquery.

    Handles related_via_attribute for attributes accessed through relations.

    Args:
        attribute: The Attribute instance
        value_condition: Q object for value comparison
        related_vias: Dict mapping attribute_id to related_via configurations

    Returns:
        Q: Q object with EXISTS subquery
    """
    model = ServerAttribute.get_model(attribute.type)
    if model is None:
        raise FilterValueError(f'Unknown attribute type: {attribute.type}')

    # Check for special markers
    negate = False
    empty_filter = False

    if hasattr(value_condition, 'children'):
        new_children = []
        for child in value_condition.children:
            if isinstance(child, tuple):
                key, val = child
                if key == '_boolean_negate':
                    negate = val
                    continue
                if key == '_empty_filter':
                    empty_filter = True
                    continue
            new_children.append(child)
        value_condition.children = new_children

    # Get related_via configurations for this attribute
    attr_related_vias = related_vias.get(attribute.attribute_id, {})
    if not attr_related_vias:
        # Direct lookup only
        attr_related_vias = {None: []}

    # Build conditions for each related_via path
    relation_conditions = []
    for related_via_attribute, servertype_ids in attr_related_vias.items():
        relation_condition = _build_related_via_condition(
            attribute, model, value_condition, related_via_attribute, empty_filter
        )
        relation_conditions.append((relation_condition, servertype_ids))

    # Combine with OR, adding servertype filter if multiple paths
    if len(relation_conditions) == 1:
        result = relation_conditions[0][0]
    else:
        # Build OR combination without starting with FALSE
        # This avoids the inefficient "(pk IS NULL AND pk IS NOT NULL) OR ..." pattern
        combined = None
        for condition, servertype_ids in relation_conditions:
            term = (condition & Q(servertype_id__in=servertype_ids)) if servertype_ids else condition
            if combined is None:
                combined = term
            else:
                combined |= term
        result = combined if combined is not None else Q(pk__in=[])  # Empty result if no conditions

    return ~result if negate else result


def _build_related_via_condition(attribute, model, value_condition, related_via, empty_filter):
    """
    Build EXISTS condition for a specific related_via path.

    Args:
        attribute: The target attribute
        model: The ServerAttribute subclass model
        value_condition: Q object for value comparison
        related_via: The related_via Attribute or None for direct
        empty_filter: Whether this is an Empty filter

    Returns:
        Q: EXISTS subquery condition
    """
    base_filter = Q(attribute_id=attribute.attribute_id)

    if not empty_filter and value_condition.children:
        # Apply value condition, handling inet operators
        base_filter &= _apply_value_condition(model, value_condition)

    if related_via is None:
        # Direct: server.server_id = sub.server_id
        exists_query = model.objects.filter(
            server_id=OuterRef('server_id'),
        ).filter(base_filter)
    elif related_via.type == 'supernet':
        # Complex inet containment join
        exists_query = _build_supernet_related_query(
            attribute, model, base_filter, related_via
        )
    elif related_via.type == 'reverse':
        # Join through reversed relation.
        # We must use RawSQL to reference "server"."server_id" directly because
        # OuterRef('server_id') in a nested Subquery would incorrectly reference
        # the model's server_id (immediate outer query) instead of the Server table.
        exists_query = model.objects.filter(
            server_id__in=RawSQL(
                '''
                SELECT rel.server_id FROM server_relation_attribute rel
                WHERE rel.value = "server"."server_id"
                AND rel.attribute_id = %s
                ''',
                [related_via.reversed_attribute_id]
            ),
        ).filter(base_filter)
    else:
        # relation type: join through ServerRelationAttribute.
        # We must use RawSQL to reference "server"."server_id" directly because
        # OuterRef('server_id') in a nested Subquery would incorrectly reference
        # the model's server_id (immediate outer query) instead of the Server table.
        exists_query = model.objects.filter(
            server_id__in=RawSQL(
                '''
                SELECT rel.value FROM server_relation_attribute rel
                WHERE rel.server_id = "server"."server_id"
                AND rel.attribute_id = %s
                ''',
                [related_via.attribute_id]
            ),
        ).filter(base_filter)

    result = Exists(exists_query)
    return ~result if empty_filter else result


def _apply_value_condition(model, value_condition):
    """
    Apply value condition to model, handling special inet operators.

    Args:
        model: The ServerAttribute subclass model
        value_condition: Q object with value comparisons

    Returns:
        Q: Transformed Q object
    """
    if model == ServerInetAttribute:
        return _transform_inet_condition(value_condition)
    return value_condition


def _transform_inet_condition(value_condition):
    """
    Transform inet-specific Q markers to RawSQL expressions.

    Args:
        value_condition: Q object potentially containing inet markers

    Returns:
        Q: Q object with RawSQL for inet operations
    """
    if not hasattr(value_condition, 'children'):
        return value_condition

    transformed = Q()
    for child in value_condition.children:
        if isinstance(child, tuple):
            key, val = child
            if key == '_inet_contains':
                # >>= operator
                transformed.children.append(
                    ('pk__in', RawSQL(
                        'SELECT id FROM server_inet_attribute WHERE value >>= %s',
                        [val]
                    ))
                )
            elif key == '_inet_contained_by':
                # <<= operator
                transformed.children.append(
                    ('pk__in', RawSQL(
                        'SELECT id FROM server_inet_attribute WHERE value <<= %s',
                        [val]
                    ))
                )
            elif key == '_inet_overlaps':
                # && operator
                transformed.children.append(
                    ('pk__in', RawSQL(
                        'SELECT id FROM server_inet_attribute WHERE value && %s',
                        [val]
                    ))
                )
            elif key == '_inet_contained_only_by':
                # << with no intermediate supernet
                transformed.children.append(
                    ('pk__in', RawSQL(
                        'SELECT id FROM server_inet_attribute WHERE value << %s',
                        [val]
                    ))
                )
            elif key == '_string_contained_by':
                # Reverse contains for string
                transformed.children.append(
                    ('pk__in', RawSQL(
                        "SELECT id FROM server_string_attribute WHERE %s LIKE '%%' || value || '%%'",
                        [val]
                    ))
                )
            else:
                transformed.children.append(child)
        elif isinstance(child, Q):
            transformed.children.append(_transform_inet_condition(child))
        else:
            transformed.children.append(child)

    transformed.connector = value_condition.connector
    transformed.negated = value_condition.negated
    return transformed


def _build_supernet_lookup(attribute, value_condition):
    """
    Build lookup for supernet attribute type.

    For supernet attributes, we find servers whose inet attribute contains
    the current server's inet, then filter those by the value_condition
    (which applies to the supernet server's hostname).

    PERFORMANCE: The hostname filter must be a NON-CORRELATED subquery so it's
    evaluated once, not per-row. This matches v1's efficient structure:
      supernet.server_id IN (SELECT server_id FROM server WHERE hostname = ...)

    Args:
        attribute: Supernet attribute instance
        value_condition: Q object for value comparison (applied to hostname)

    Returns:
        Q: EXISTS subquery for supernet matching
    """
    # Build the inet address family filter if needed
    af_condition = ''
    af_join = ''
    if attribute.inet_address_family:
        af_condition = (
            f"AND server_attr.inet_address_family = '{attribute.inet_address_family}' "
            f"AND net_attr.inet_address_family = '{attribute.inet_address_family}' "
        )
        af_join = (
            'JOIN attribute AS server_attr ON server_attr.attribute_id = server_addr.attribute_id '
            'JOIN attribute AS net_attr ON net_attr.attribute_id = net_addr.attribute_id '
        )

    # Convert value_condition to SQL for the hostname filter.
    # This will be embedded as a NON-CORRELATED subquery for efficiency.
    hostname_filter_sql, hostname_params = _build_hostname_filter_sql(value_condition)

    # Build efficient EXISTS query matching v1's structure:
    # - Single EXISTS with all conditions
    # - Hostname filter as non-correlated subquery (evaluated once)
    # - Inet containment as the correlated part
    return Exists(
        RawSQL(
            f'''
            SELECT 1 FROM server AS supernet
            JOIN server_inet_attribute AS net_addr ON net_addr.server_id = supernet.server_id
            JOIN server_inet_attribute AS server_addr ON server_addr.server_id = "server"."server_id"
            {af_join}
            WHERE net_addr.value >>= server_addr.value
            AND net_addr.attribute_id = server_addr.attribute_id
            AND supernet.servertype_id = %s
            AND supernet.server_id IN (
                SELECT server_id FROM server WHERE {hostname_filter_sql}
            )
            {af_condition}
            ''',
            [attribute.target_servertype_id] + hostname_params
        )
    )


def _build_hostname_filter_sql(value_condition):
    """
    Convert a value condition Q object to SQL for hostname filtering.

    Args:
        value_condition: Q object with value__* lookups

    Returns:
        tuple: (sql_string, params_list)
    """
    # Extract the filter from the Q object
    if not hasattr(value_condition, 'children') or not value_condition.children:
        # Empty condition - match all
        return 'TRUE', []

    for child in value_condition.children:
        if isinstance(child, tuple):
            key, val = child

            # Handle common lookup types
            if key in ('value', 'value__exact'):
                return '"hostname" = %s', [val]
            elif key == 'value__regex':
                return '"hostname" ~ %s', [val]
            elif key == 'value__iregex':
                return '"hostname" ~* %s', [val]
            elif key == 'value__contains':
                return '"hostname" LIKE %s', [f'%{val}%']
            elif key == 'value__icontains':
                return '"hostname" ILIKE %s', [f'%{val}%']
            elif key == 'value__startswith':
                return '"hostname" LIKE %s', [f'{val}%']
            elif key == 'value__istartswith':
                return '"hostname" ILIKE %s', [f'{val}%']
            elif key == 'value__endswith':
                return '"hostname" LIKE %s', [f'%{val}']
            elif key == 'value__iendswith':
                return '"hostname" ILIKE %s', [f'%{val}']
            elif key == 'value__gt':
                return '"hostname" > %s', [val]
            elif key == 'value__gte':
                return '"hostname" >= %s', [val]
            elif key == 'value__lt':
                return '"hostname" < %s', [val]
            elif key == 'value__lte':
                return '"hostname" <= %s', [val]
            elif key == 'value__in':
                placeholders = ', '.join(['%s'] * len(val))
                return f'"hostname" IN ({placeholders})', list(val)

    # Fallback: try to handle negated conditions
    if value_condition.negated and value_condition.children:
        inner_sql, inner_params = _build_hostname_filter_sql(
            Q(*value_condition.children, _connector=value_condition.connector)
        )
        return f'NOT ({inner_sql})', inner_params

    # Last resort fallback - match all (shouldn't normally reach here)
    return 'TRUE', []


def _transform_to_server_id(value_condition):
    """Transform value lookups to server_id lookups."""
    if not hasattr(value_condition, 'children'):
        return value_condition

    transformed = Q()
    for child in value_condition.children:
        if isinstance(child, tuple):
            key, val = child
            if key.startswith('value'):
                new_key = key.replace('value', 'server_id', 1)
                transformed.children.append((new_key, val))
            else:
                transformed.children.append(child)
        elif isinstance(child, Q):
            transformed.children.append(_transform_to_server_id(child))
        else:
            transformed.children.append(child)

    transformed.connector = value_condition.connector
    transformed.negated = value_condition.negated
    return transformed


def _build_domain_lookup(attribute, value_condition):
    """
    Build lookup for domain attribute type.

    Args:
        attribute: Domain attribute instance
        value_condition: Q object for value comparison

    Returns:
        Q: EXISTS subquery for domain matching
    """
    # Domain lookup matches servers whose hostname is a subdomain
    return Exists(
        Server.objects.filter(
            servertype_id=attribute.target_servertype_id,
        ).extra(
            where=[
                "server.hostname ~ ('^[^\\.]+\\.' || regexp_replace("
                "server.hostname, '(\\*|\\-|\\.)', '\\\\\\1', 'g') || '$')"
            ],
            tables=['server AS outer_server'],
        ).filter(
            _transform_to_server_id(value_condition)
        )
    )


def _build_reverse_lookup(attribute, value_condition):
    """
    Build lookup for reverse attribute type.

    Args:
        attribute: Reverse attribute instance
        value_condition: Q object for value comparison

    Returns:
        Q: EXISTS subquery for reverse relation matching
    """
    return Exists(
        ServerRelationAttribute.objects.filter(
            attribute_id=attribute.reversed_attribute_id,
            value=OuterRef('server_id'),
        ).filter(
            server_id__in=Subquery(
                Server.objects.filter(
                    _transform_to_server_id(value_condition)
                ).values('server_id')
            )
        )
    )


def _build_supernet_related_query(attribute, model, base_filter, related_via):
    """
    Build query for attributes accessed through supernet relation.

    This handles the case where an attribute is accessed via a supernet
    relationship. For example, if server A has inet 10.0.0.1 and server B
    (a network) has inet 10.0.0.0/24, then attributes on B can be accessed
    from A via the supernet relation.

    PERFORMANCE: The query structure must put the attribute filter FIRST, then
    check supernet containment with a link to the attribute row. This matches
    v1's efficient structure:
        SELECT 1 FROM attribute_table sub
        WHERE sub.attribute_id = X AND sub.value = Y  -- Filter FIRST
        AND EXISTS (supernet check WHERE supernet.server_id = sub.server_id)

    This allows PostgreSQL to:
    1. First filter to the small set of attribute rows matching the value
    2. Only then check inet containment for those rows

    Args:
        attribute: Target attribute
        model: ServerAttribute model class
        base_filter: Q object with attribute_id and value filter
        related_via: The supernet attribute used for relation

    Returns:
        QuerySet: Query for EXISTS check (with RawSQL for supernet correlation)
    """
    # Build inet address family filter if needed
    af_condition = ''
    af_join = ''
    if related_via.inet_address_family:
        af_condition = (
            f"AND server_attr.inet_address_family = '{related_via.inet_address_family}' "
            f"AND net_attr.inet_address_family = '{related_via.inet_address_family}' "
        )
        af_join = (
            'JOIN attribute AS server_attr ON server_attr.attribute_id = server_addr.attribute_id '
            'JOIN attribute AS net_attr ON net_attr.attribute_id = net_addr.attribute_id '
        )

    # Build the inner EXISTS that checks supernet containment.
    # The key is "supernet.server_id = {outer_alias}.server_id" which links the
    # supernet to the attribute row, allowing the attribute filter to run first.
    #
    # We use the model's table name to reference the outer query in the EXISTS.
    # Django aliases subquery tables, but we can use a correlated reference.
    model_table = model._meta.db_table

    # The supernet EXISTS checks:
    # 1. supernet.server_id = sub.server_id (links supernet to attribute row)
    # 2. supernet contains the outer server's inet
    supernet_exists_sql = RawSQL(
        f'''
        EXISTS (
            SELECT 1 FROM server AS supernet
            JOIN server_inet_attribute AS net_addr ON net_addr.server_id = supernet.server_id
            JOIN server_inet_attribute AS server_addr ON server_addr.server_id = "server"."server_id"
            {af_join}
            WHERE net_addr.value >>= server_addr.value
            AND net_addr.attribute_id = server_addr.attribute_id
            AND supernet.servertype_id = %s
            AND supernet.server_id = "{model_table}"."server_id"
            {af_condition}
        )
        ''',
        [related_via.target_servertype_id]
    )

    # Return query with attribute filter FIRST, then supernet EXISTS
    # This allows PostgreSQL to filter by attribute value before checking containment
    return model.objects.filter(base_filter).extra(
        where=[supernet_exists_sql.sql],
        params=supernet_exists_sql.params
    )
