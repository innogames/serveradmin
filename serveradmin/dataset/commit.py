import time
import json

from django.db import connection

from adminapi.dataset.exceptions import (
        CommitValidationFailed,
        CommitNewerData,
        CommitError,
    )
from adminapi.utils.json import json_encode_extra
from serveradmin.dataset.base import lookups, ServerTableSpecial
from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import ChangeCommit, ChangeUpdate, ChangeDelete

def commit_changes(
        commit,
        skip_validation=False,
        force_changes=False,
        app=None,
        user=None,
    ):
    """Commit server changes to the database after validation.

    :param commit: Dictionary with the keys 'deleted' and 'changes' containing
                   a list of deleted servers and a dictionary of the servers'
                   changes.
    """

    deleted_servers = commit.get('deleted', [])
    changed_servers = commit.get('changes', {})

    _validate_structure(deleted_servers, changed_servers)
    _typecast_values(changed_servers)
    _clean_changed(changed_servers)

    if not changed_servers and not deleted_servers:
        return

    with connection.cursor() as cursor:
        cursor.execute(u"SELECT GET_LOCK('serverobject_commit', 10)")

        try:
            if not cursor.fetchone()[0]:
                raise CommitError(u'Could not get lock')

            servers = _fetch_servers(changed_servers)

            # Attributes must be always validated
            violations_attribs = _validate_attributes(changed_servers, servers)
            if not skip_validation:
                violations_readonly = _validate_readonly(changed_servers, servers)
                violations_regexp = _validate_regexp(changed_servers, servers)
                violations_required = _validate_required(changed_servers, servers)
                if (violations_attribs or violations_readonly or
                    violations_regexp or violations_required):
                    error_message = _build_error_message(
                            violations_attribs,
                            violations_readonly,
                            violations_regexp,
                            violations_required,
                        )
                    raise CommitValidationFailed(error_message,
                            violations_attribs + violations_readonly +
                            violations_regexp + violations_required,
                        )
            if violations_attribs:
                error_message = _build_error_message(violations_attribs, [], [])
                raise CommitValidationFailed(error_message, violations_attribs)
            if not force_changes:
                newer = _validate_commit(changed_servers, servers)
                if newer:
                    raise CommitNewerData(u'Newer data available', newer)

            _log_changes(deleted_servers, changed_servers, app, user)
            if deleted_servers:
                _delete_servers(deleted_servers)
            _apply_changes(changed_servers, servers)

        finally:
            cursor.execute(u'COMMIT')
            cursor.execute(u"SELECT RELEASE_LOCK('serverobject_commit')")

def _log_changes(deleted_servers, changed_servers, app, user):
    # Import here to break cyclic import
    from serveradmin.dataset import query, filters

    if deleted_servers:
        old_servers = list(query(object_id=filters.Any(*deleted_servers)))
    else:
        old_servers = []

    servers = (query(object_id=filters.Any(*changed_servers.keys()))
            .restrict('hostname'))
    changes = {}
    for server_obj in servers:
        changes[server_obj['hostname']] = changed_servers[server_obj.object_id]

    if not (changes or old_servers):
        return

    commit = ChangeCommit.objects.create(app=app, user=user)
    for hostname, updates in changes.items():
        ChangeUpdate.objects.create(
                commit=commit,
                hostname=hostname,
                updates_json=json.dumps(updates, default=json_encode_extra),
            )
    for attributes in old_servers:
        attributes_json = json.dumps(attributes, default=json_encode_extra)
        ChangeDelete.objects.create(
                commit=commit,
                hostname=attributes['hostname'],
                attributes_json=attributes_json,
            )

def _fetch_servers(changed_servers):
    # Import here to break cyclic import
    from serveradmin.dataset.queryset import QuerySet
    from serveradmin.dataset.filters import Any
    # Only load attributes that will be changed (for performance reasons)
    changed_attrs = set([u'servertype'])
    for changes in changed_servers.itervalues():
        for attr in changes:
            changed_attrs.add(attr)

    queryset = QuerySet({'object_id': Any(*changed_servers.keys())})
    queryset.restrict(*changed_attrs)

    return queryset.get_raw_results()

def _validate_structure(deleted_servers, changed_servers):
    if not isinstance(deleted_servers, (list, set)):
        raise ValueError(u'Invalid deleted servers')
    if not all(isinstance(x, (int, long)) for x in deleted_servers):
        raise ValueError(u'Invalid deleted servers')

    # FIXME: Validation of the inner structure
    for server_id, changes in changed_servers.iteritems():
        for attr, change in changes.iteritems():
            if attr not in lookups.attr_names:
                raise ValueError(u'No such attribute')
            action = change[u'action']
            if action == u'update':
                if not all(x in change for x in (u'old', u'new')):
                    raise ValueError(u'Invalid update change')
            elif action == u'new':
                if u'new' not in change:
                    raise ValueError(u'Invalid new change')
            elif action == u'delete':
                if u'old' not in change:
                    raise ValueError(u'Invalid delete change')
            elif action == u'multi':
                if not all(x in change for x in (u'add', u'remove')):
                    raise ValueError(u'Invalid multi change')
                if not lookups.attr_names[attr].multi:
                    raise ValueError(u'Not a multi attribute')

def _validate_attributes(changed_servers, servers):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            if attr == u'servertype':
                raise CommitValidationFailed(u'Cannot change servertype', [])

            if (server[u'servertype'], attr) not in lookups.stype_attrs:
                violations.append((server_id, attr))
    return violations

def _validate_readonly(changed_servers, servers):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            if lookups.attr_names[attr].readonly:
                if attr in server and server[attr] != '':
                    violations.append((server_id, attr))
    return violations

def _validate_regexp(changed_servers, servers):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            index = (server[u'servertype'], attr)
            try:
                regexp = lookups.stype_attrs[index].regexp
            except KeyError:
                continue
            action = change[u'action']
            if action == u'update' or action == u'new':
                if regexp and not regexp.match(change[u'new']):
                        violations.append((server_id, attr))
            elif action == u'multi':
                for value in change[u'add']:
                    if regexp and not regexp.match(value):
                        violations.append((server_id, attr))
                        break
    return violations

def _validate_required(changed_servers, servers):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            index = (server[u'servertype'], attr)
            try:
                required = lookups.stype_attrs[index].required
            except KeyError:
                continue
            if change[u'action'] == u'delete' and required:
                violations.append((server_id, attr))
    return violations

def _validate_commit(changed_servers, servers):
    newer = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            action = change[u'action']
            if action == u'new':
                if attr in server:
                    newer.append((server_id, attr, server[attr]))
            elif action == u'update' or action == u'delete':
                try:
                    if server[attr] != change[u'old']:
                        newer.append((server_id, attr, server[attr]))
                except KeyError:
                    newer.append((server_id, attr, None))
    return newer

def _typecast_values(changed_servers):
    for server_id, changes in changed_servers.iteritems():
        for attr, change in changes.iteritems():
            action = change['action']
            if action == 'new':
                change['new'] = typecast(attr, change['new'])
            elif action == 'update':
                change['new'] = typecast(attr, change['new'])
                change['old'] = typecast(attr, change['old'])
            elif action == 'multi':
                change['add'] = typecast(attr, change['add'])
                change['remove'] = typecast(attr, change['remove'])
            elif action == 'delete':
                change['old'] = typecast(attr, change['old'])

def _clean_changed(changed_servers):
    for server_id, changes in changed_servers.items():
        server_changed = False
        for attr, change in changes.items():
            action = change['action']
            if action == 'new':
                server_changed = True
            elif action == 'update':
                if change['old'] != change['new']:
                    server_changed = True
                else:
                    del changes[attr]
            elif action == 'multi':
                if change['add'] or change['remove']:
                    intersect = change['add'].intersection(change['remove'])
                    if intersect:
                        for value in intersect:
                            change['add'].remove(value)
                            change['remove'].remove(value)
                    if change['add'] or change['remove']:
                        server_changed = True
                    else:
                        del changes[attr]
                else:
                    del changes[attr]
            elif action == 'delete':
                server_changed = True
        if not server_changed:
            del changed_servers[server_id]

def _delete_servers(deleted_servers):
    ids = ', '.join(str(x) for x in deleted_servers)
    with connection.cursor() as cursor:
        cursor.execute(u'DELETE FROM attrib_values WHERE server_id IN ({0})'.format(ids))
        cursor.execute(u'DELETE FROM admin_server WHERE server_id IN ({0})'.format(ids))

def _apply_changes(changed_servers, servers):

    query_update = (
            u'UPDATE attrib_values SET value=%s '
            u'WHERE server_id = %s AND attrib_id = %s'
        )
    query_insert = (
            u'INSERT INTO attrib_values (server_id, attrib_id, value) '
            u'VALUES (%s, %s, %s)'
        )
    query_remove = (
            u'DELETE FROM attrib_values '
            u'WHERE server_id = %s AND attrib_id = %s AND value=%s'
        )
    query_remove_all = (
            u'DELETE FROM attrib_values '
            u'WHERE server_id = %s AND attrib_id = %s'
        )

    with connection.cursor() as cursor:
        for server_id, changes in changed_servers.iteritems():
            server = servers[server_id]
            for attr, change in changes.iteritems():
                attr_obj = lookups.attr_names[attr]
                attr_id = attr_obj.pk

                action = change[u'action']

                # XXX Dirty hack for old database structure
                if isinstance(attr_obj.special, ServerTableSpecial):
                    field = attr_obj.special.field
                    query = u'UPDATE admin_server SET {0} = %s WHERE server_id = %s'
                    if action == 'new' or action == 'update':
                        value = _prepare_value(attr, change[u'new'])
                        cursor.execute(query.format(field), (value, server_id))
                    elif action == 'delete':
                        # FIXME: This might fail if field it not NULLable
                        cursor.execute(query.format(field), (None, server_id))
                    continue

                if action == u'new' or action == u'update':
                    value = _prepare_value(attr, change[u'new'])
                    if attr in server:
                        cursor.execute(query_update, (value, server_id, attr_id))
                    else:
                        cursor.execute(query_insert, (server_id, attr_id, value))
                elif action == u'delete':
                    cursor.execute(query_remove_all, (server_id, attr_id))
                elif action == u'multi':
                    for value in change[u'remove']:
                        value = _prepare_value(attr, value)
                        cursor.execute(query_remove, (server_id, attr_id, value))
                    for value in change[u'add']:
                        value = _prepare_value(attr, value)
                        if value in server[attr]:
                            continue # Avoid duplicate entries
                        cursor.execute(query_insert, (server_id, attr_id, value))
        cursor.execute('COMMIT')

def _prepare_value(attr_name, value):
    if value is None:
        raise ValueError('Value is empty')
    attr_obj = lookups.attr_names[attr_name]
    if attr_obj.type == u'ip':
        value = value.as_int()
    elif attr_obj.type == u'ipv6':
        value = value.as_hex()
    elif attr_obj.type == u'datetime':
        value = int(time.mktime(value.timetuple()))
    return value

def _build_error_message(violations_attribs, violations_readonly,
                         violations_regexp, violations_required):

    violation_types = [
            (violations_attribs, 'Attribute not on servertype'),
            (violations_readonly, 'Attribute is read-only'),
            (violations_regexp, 'Regexp does not match'),
            (violations_required, 'Attribute is required'),
        ]

    message = []
    for violations, message_type in violation_types:
        seen = {}
        for server_id, vattr in violations:
            if vattr in seen:
                seen[vattr] += 1
            else:
                seen[vattr] = 1

        if seen:
            for vattr, num_affected in seen.iteritems():
                message.append(u'{0}: {1} (#affected: {2})'.format(
                        message_type, vattr, num_affected
                    ))

    return u'. '.join(message)
