# SQL Generator V2 - Implementation Context

## Overview

This document provides context for continuing development on the SQL Generator V2 rewrite for the serveradmin project. The goal is to replace raw SQL string concatenation with Django ORM for improved security and maintainability.

## Project Structure

```
serveradmin/serverdb/
├── sql_generator.py          # Original v1 (raw SQL) - UNCHANGED
├── sql_generator_v2.py       # New v2 (Django ORM) - NEW
├── query_builder.py          # Facade for switching v1/v2 - NEW
├── query_executer.py         # Modified to use facade
└── tests/
    └── test_sql_generator_v2.py  # Unit tests - NEW
```

## Configuration

Switch between implementations via Django setting in `serveradmin/settings.py`:
```python
SQL_GENERATOR_VERSION = env('SQL_GENERATOR_VERSION', default='v1')  # 'v1' or 'v2'
```

## Key Design Decisions

### 1. Return Type Difference
- **V1**: Returns raw SQL string
- **V2**: Returns Django QuerySet

`query_executer.py` handles both:
```python
if isinstance(query_result, str):
    return list(Server.objects.defer('intern_ip').raw(query_result))
else:
    return list(query_result)  # No defer() - causes N+1 queries!
```

### 2. OuterRef Limitations
Django's `OuterRef` only references the **immediate outer query**. For nested subqueries, use `RawSQL` with direct table references like `"server"."server_id"`.

**Wrong** (causes "can't adapt type 'OuterRef'" error):
```python
server_id__in=Subquery(
    SomeModel.objects.filter(server_id=OuterRef('server_id'))  # References wrong table!
)
```

**Correct**:
```python
server_id__in=RawSQL(
    'SELECT ... WHERE server_id = "server"."server_id"',  # Direct reference
    []
)
```

### 3. Performance: Non-Correlated Subqueries
For supernet lookups, hostname filters must be **non-correlated** (evaluated once):

**Slow** (hostname filter after correlated subquery):
```sql
EXISTS (SELECT FROM server U0 WHERE U0.id IN (correlated) AND U0.hostname = 'x')
```

**Fast** (hostname filter as non-correlated subquery):
```sql
EXISTS (SELECT FROM server supernet ...
        AND supernet.id IN (SELECT id FROM server WHERE hostname = 'x'))
```

## Commits Made (on branch `dk_sql_generator_v3`)

1. `e2963275` - Initial implementation with facade, settings, v2 module, tests
2. `007a43ce` - Fix OuterRef error in supernet-related queries
3. `7df4a43a` - Fix N+1 query (remove defer('intern_ip') for v2)
4. `104fa652` - Fix related_via for relation/reverse types (OuterRef bug)
5. `1ebb835e` - Optimize supernet lookup with non-correlated hostname subquery

## Key Functions in sql_generator_v2.py

### Entry Point
- `get_server_query(attribute_filters, related_vias)` → Returns QuerySet

### Filter Building
- `_build_attribute_condition(attribute, filt, related_vias)` → Q object
- `_build_value_condition(attribute, filt)` → Q object for value comparison
- `_build_logical_condition(attribute, filt, related_vias)` → Handles Any/All/Not

### Attribute Lookups
- `_build_attribute_lookup(attribute, value_condition, related_vias)` → Routes to specific builders
- `_build_special_lookup(attribute, value_condition)` → hostname, servertype, object_id, intern_ip
- `_build_standard_lookup(attribute, value_condition, related_vias)` → Regular attributes
- `_build_supernet_lookup(attribute, value_condition)` → Supernet type (inet containment)
- `_build_domain_lookup(attribute, value_condition)` → Domain type
- `_build_reverse_lookup(attribute, value_condition)` → Reverse relations

### Related Via Handling
- `_build_related_via_condition(attribute, model, value_condition, related_via, empty_filter)`
- `_build_supernet_related_query(attribute, model, base_filter, related_via)`

### Helpers
- `_build_hostname_filter_sql(value_condition)` → Converts Q to SQL for hostname
- `_transform_to_hostname(value_condition)` → Transforms value→hostname lookups
- `_transform_inet_condition(value_condition)` → Handles inet operators
- `_apply_value_condition(model, value_condition)` → Applies inet transforms if needed

## Data Model Summary

### Key Models
- `Server` - Main entity (server_id, hostname, intern_ip, servertype_id)
- `Attribute` - Attribute definitions (type: string, boolean, relation, inet, supernet, domain, reverse, etc.)
- `ServertypeAttribute` - Links servertypes to attributes, has `related_via_attribute`
- `ServerStringAttribute`, `ServerRelationAttribute`, `ServerInetAttribute`, etc. - Attribute values

### Special Attributes (hardcoded)
- `object_id` → server.server_id
- `hostname` → server.hostname
- `servertype` → server.servertype_id
- `intern_ip` → server.intern_ip

### related_vias Dictionary
Structure: `{attribute_id: {related_via_attribute: [servertype_ids]}}`
- `related_via_attribute = None` → Direct lookup
- `related_via_attribute.type = 'relation'` → Follow relation to target server
- `related_via_attribute.type = 'reverse'` → Follow reverse relation
- `related_via_attribute.type = 'supernet'` → Inet containment lookup

## Filter Types (from adminapi/filters.py)

| Filter | Django ORM | SQL |
|--------|-----------|-----|
| BaseFilter | `__exact` | `= 'value'` |
| Regexp | `__regex` | `~ 'pattern'` |
| GreaterThan | `__gt` | `> value` |
| Contains (string) | `__contains` | `LIKE '%value%'` |
| Contains (inet) | RawSQL | `>>= 'network'` |
| ContainedBy (inet) | RawSQL | `<<= 'network'` |
| Overlaps (inet) | RawSQL | `&& 'network'` |
| Any | `Q() \| Q()` | `OR` |
| All | `Q() & Q()` | `AND` |
| Not | `~Q()` | `NOT` |
| Empty | Check EXISTS | `IS NOT NULL` then negate |

## Known Issues / TODOs

1. **ContainedOnlyBy filter** - Not fully implemented (raises NotImplementedError in filters.py)
2. **Domain type lookups** - Uses `.extra()` which is deprecated
3. **Complex nested logical filters** - May need more testing
4. **Inet operators** - Using RawSQL with table name assumptions

## Testing

Run tests:
```bash
python manage.py test serveradmin.serverdb.tests.test_sql_generator_v2
```

Test categories:
- `TestGetServerQueryV2` - Basic functionality
- `TestSpecialAttributeFilters` - hostname, servertype, object_id
- `TestComparisonFilters` - >, <, >=, <=
- `TestLogicalFilters` - Any, All, Not
- `TestStringFilters` - Contains, StartsWith
- `TestV1V2Comparison` - Ensures v1 and v2 return same results
- `TestQueryBuilderFacade` - Switching mechanism

## Useful Queries for Testing

```
hostname=test0                    # Simple equality
servertype=vm                     # Servertype filter
responsible_admin=daniel.kroeger  # Related via attribute
network_zones=aw                  # Related via supernet
route_network=foe-aw-int          # Supernet type attribute
```

## Files Reference

| File | Purpose |
|------|---------|
| `serveradmin/settings.py:47` | SQL_GENERATOR_VERSION setting |
| `serveradmin/serverdb/query_builder.py` | Switching facade |
| `serveradmin/serverdb/query_executer.py:260-271` | Handles v1/v2 return types |
| `serveradmin/serverdb/sql_generator.py` | Original v1 implementation |
| `serveradmin/serverdb/sql_generator_v2.py` | New v2 implementation |
| `adminapi/filters.py` | Filter class definitions |
| `serveradmin/serverdb/models.py` | Django models |
