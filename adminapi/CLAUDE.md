## Overview

`adminapi` is a Python library for interacting with Serveradmin, a system for querying and managing server attributes. It provides both a Python API and a CLI tool for server management operations.

Documentation: https://serveradmin.readthedocs.io/en/latest/python-api.html

## Development Commands

### Setup
```bash
# Install from parent directory, like
cd ~/projects/serveradmin
pip install -e .
```

### Testing
```bash
# Run all tests
python -m unittest discover adminapi/tests

# Run specific test file
python -m unittest adminapi.tests.test_cli
python -m unittest adminapi.tests.test_dataset

# Run single test
python -m unittest adminapi.tests.test_cli.TestCommandlineInterface.test_one_argument
```

### CLI Usage
```bash
# Query servers
adminapi 'hostname=web01'
adminapi 'project=adminapi' --attr hostname --attr state

# Update servers
adminapi 'hostname=web01' --update state=maintenance
```

### Python API Examples

**Query and modify servers**
```python
from adminapi.dataset import Query

# Query servers matching criteria
servers = Query({
    'servertype': 'vm',
    'project': 'test_project',
    'state': 'offline',
})

# Modify server attributes
for server in servers:
    print(f"Bringing {server['hostname']} online")
    server['state'] = 'online'

# Commit changes to persist them
servers.commit()
```

**Query with restricted attributes**
```python
from adminapi.dataset import Query

# Only fetch specific attributes to reduce payload
servers = Query(
    {'project': 'test_project', 'state': 'maintenance'},
    restrict=['hostname', 'state']
)

for server in servers:
    print(f"{server['hostname']}: {server['state']}")
```

**Get single server**
```python
from adminapi.dataset import Query

# Use get() when expecting exactly one result
server = Query({'hostname': 'web01'}).get()
server['state'] = 'maintenance'
server.commit()
```

## Architecture

### Core Components

**Query System** (`dataset.py`)
- `Query`: Main class for filtering and fetching server objects from Serveradmin
- `BaseQuery`: Base class with common query operations (filtering, ordering, committing)
- Queries are lazy-loaded and cached until explicitly fetched
- Always ensures `object_id` is included in restrict lists for correlation during commits

**Data Objects** (`dataset.py`)
- `DatasetObject`: Dict-like wrapper for server data with change tracking
- `MultiAttr`: Set-like wrapper for multi-value attributes with automatic change propagation
- Track state: `created`, `changed`, `deleted`, or `consistent`
- Old values stored in `old_values` dict for rollback/commit operations

**Filters** (`filters.py`)
- `BaseFilter`: Exact match filter (default)
- Comparison: `GreaterThan`, `LessThan`, `GreaterThanOrEquals`, `LessThanOrEquals`
- Pattern: `Regexp`, `StartsWith`, `Contains`, `ContainedBy`, `Overlaps`
- Logical: `Any` (OR), `All` (AND), `Not`
- Special: `Empty` (null check), `ContainedOnlyBy` (IP network containment)

**Request Layer** (`request.py`)
- Handles HTTP communication with Serveradmin server
- Authentication via SSH keys (paramiko), SSH agent, or auth tokens (HMAC-SHA1)
- Automatic retry logic (3 attempts, 5s interval) for network failures
- Gzip compression support for responses
- Environment variables: `SERVERADMIN_BASE_URL`, `SERVERADMIN_KEY_PATH`, `SERVERADMIN_TOKEN`

**Query Parser** (`parse.py`)
- Converts string queries to filter dictionaries
- Supports function syntax: `attribute=Function(value)`
- Regex detection: triggers `Regexp` filter for patterns with `.*`, `.+`, `[`, `]`, etc.
- Hostname shorthand: first token without `=` treated as hostname filter

**API Calls** (`api.py`)
- `FunctionGroup`: Dynamic proxy for calling Serveradmin API functions
- Pattern: `FunctionGroup('group_name').function_name(*args, **kwargs)`
- Example: `api.get('nagios').commit('push', 'user', project='foo')`

### Data Flow

1. **Query Construction**: Create `Query` with filters dict, restrict list, order_by
2. **Lazy Fetch**: Results fetched on first iteration/access via `_get_results()`
3. **Modification**: Change `DatasetObject` attributes, tracked in `old_values`
4. **Commit**: Build commit object with created/changed/deleted arrays, send to server
5. **Confirm**: Clear `old_values`, update object state after successful commit

### Change Tracking

- **Single attributes**: Save original value on first modification to `old_values`
- **Multi attributes**: `MultiAttr` operations create new sets, trigger parent `__setitem__`
- **Validation**: Type checking against existing attribute types (bool, multi, datatype)
- **Serialization**: Changed objects serialize with action (`update` or `multi`) and old/new values

### Authentication Flow

1. Check for `SERVERADMIN_KEY_PATH` → load private key file
2. Else check for `SERVERADMIN_TOKEN` → use HMAC authentication
3. Else try SSH agent (`paramiko.agent.Agent`)
4. Sign timestamp + request body, include signature in `X-Signatures` header
5. Server validates signature using stored public key

## Important Patterns

- Always use `commit()` after modifying objects to persist changes
- Use `restrict` parameter to limit fetched attributes (reduces payload size)
- `get()` expects exactly one result; use for single-server queries
- Multi-value attributes must be modified via `MultiAttr` methods or reassignment
- Query filters are immutable; changes create new filter instances
- The API is marked as draft and may change in future versions
