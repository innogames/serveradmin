from django.db import connection

from serveradmin.dataset.base import lookups
from serveradmin.dataset.cache import invalidate_cache
from adminapi.dataset.exceptions import (CommitValidationFailed, CommitNewerData,
        CommitError)

def commit_changes(commit, skip_validation=False, force_changes=False):
    """Commit server changes to the database after validation.

    :param commit: Dictionary with the keys 'deleted' and 'changes' containing
                   a list of deleted servers and a dictionary of the servers'
                   changes.
    """
    deleted_servers = commit.get('deleted', [])
    changed_servers = commit.get('changes', {})

    _validate_structure(deleted_servers, changed_servers) 
    
    # FIXME: put it into lookups?
    c = connection.cursor()
    c.execute(u"SELECT GET_LOCK('serverobject_commit', 10)")
    try:
        if not c.fetchone()[0]:
            raise CommitError(u'Could not get lock')
        servers = _fetch_servers(changed_servers)
        
        # Attributes must be always validated
        violations_attribs = _validate_attributes(changed_servers, servers)
        if not skip_validation:
            violations_regexp = _validate_regexp(changed_servers, servers)
            violations_required = _validate_required(changed_servers, servers)
            if violations_attribs or violations_regexp or violations_required:
                # FIXME: distinguish regexp and required
                raise CommitValidationFailed(u'Validation failed',
                        violations_attribs + violations_regexp +
                        violations_required)
        if violations_attribs:
            raise CommitValidationFailed(u'Unskippable validation failed',
                    violations_attribs)
        if not force_changes:
            newer = _validate_commit(changed_servers, servers)
            if newer:
                raise CommitNewerData(u'Newer data available', newer)
        
        if deleted_servers:
            _delete_servers(deleted_servers)
        _apply_changes(changed_servers, servers)

        kill_cache = set()
        kill_cache.update(deleted_servers)
        kill_cache.update(changed_servers)
        
        if kill_cache:
            invalidate_cache(kill_cache)

    finally:
        c.execute(u'COMMIT')
        c.execute(u"SELECT RELEASE_LOCK('serverobject_commit')")

def _fetch_servers(changed_servers):
    # Import here to break cyclic import
    from serveradmin.dataset import query, filters
    # Only load attributes that will be changed (for performance reasons)
    changed_attrs = set([u'servertype'])
    for changes in changed_servers.itervalues():
        for attr in changes:
            changed_attrs.add(attr)
    return query(object_id=filters.Any(*changed_servers.keys())).restrict(
            *changed_attrs).get_raw_results()

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

def _delete_servers(deleted_servers):
    ids = ', '.join(str(x) for x in deleted_servers)
    c = connection.cursor()
    c.execute(u'DELETE FROM attrib_values WHERE server_id IN({0})'.format(ids))
    c.execute(u'DELETE FROM admin_server WHERE server_id IN({0})'.format(ids))

def _apply_changes(changed_servers, servers):
    c = connection.cursor()
    query_update = (u'UPDATE attrib_values SET value=%s WHERE server_id = %s '
            u'AND attrib_id = %s')
    query_insert = (u'INSERT INTO attrib_values (server_id, attrib_id, value) '
            u'VALUES (%s, %s, %s)')
    query_remove = (u'DELETE FROM attrib_values WHERE server_id = %s AND '
            u'attrib_id = %s AND value=%s')
    query_remove_all = (u'DELETE FROM attrib_values WHERE server_id = %s AND '
            u'attrib_id = %s')
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            attr_obj = lookups.attr_names[attr]
            attr_id = attr_obj.pk
            
            action = change[u'action']
            
            # FIXME
            # Quick workaround for hostname, will fix it later
            if attr_obj.name == 'hostname' and action == u'update':
                c.execute('UPDATE admin_server SET hostname=%s '
                        'WHERE server_id = %s', change[u'new'], server_id)
                continue


            if action == u'new' or action == u'update':
                if attr in server:
                    c.execute(query_update, (change[u'new'], server_id, attr_id))
                else:
                    c.execute(query_insert, (server_id, attr_id, change[u'new']))
            elif action == u'delete':
                c.execute(query_remove_all, (server_id, attr_id))
            elif action == u'multi':
                for value in change[u'remove']:
                    c.execute(query_remove, (server_id, attr_id, value))
                for value in change[u'add']:
                    if value in server[attr]:
                        continue # Avoid duplicate entries
                    c.execute(query_insert, (server_id, attr_id, value))

