import re

from django.db import connection

from serveradmin.dataset import query, filters
from serveradmin.dataset.models import ServerObject, ServerTypeAttributes
from serveradmin.dataset.base import lookups
from adminapi.dataset.base import CommitValidationFailed, CommitNewerData

def commit_changes(commit, skip_validation=False, force_changes=False):
    """Commit server changes to the database after validation.

    :param commit: Dictionary with the keys 'deleted' and 'changes' containing
                   a list of deleted servers and a dictionary of the servers'
                   changes.
    """
    deleted_servers = commit.get('deleted', [])
    changed_servers = commit.get('changes', {})

    for server_id in deleted_servers:
        ServerObject.objects.delete(server_id=server_id)
    
    if not changed_servers:
        return

    _validate_structure(changed_servers) 
    
    stype_attrs = list(ServerTypeAttributes.objects.selected_related())
    c = connection.cursor()
    c.execute('LOCK TABLE attrib_values, admin_server WRITE')
    try:
        servers = _fetch_servers(changed_servers)
        if not skip_validation:
            violations_regexp = _validate_regexp(changed_servers, servers,
                    stype_attrs)
            violations_required = _validate_required(changed_servers, servers,
                    stype_attrs)
            if violations_regexp or violations_required:
                # FIXME: distinguish regexp and required
                raise CommitValidationFailed('Validation failed',
                        violations_regexp + violations_required)
        if not force_changes:
            newer = _validate_commit(changed_servers, servers)
            if newer:
                raise CommitNewerData('Newer data available', newer)

        # FIXME: Apply changes
    finally:
        c.execute('UNLOCK TABLES')

def _fetch_servers(changed_servers):
    # Only load attributes that will be changed for performance reasons
    changed_attrs = set(['servertype'])
    for changes in changed_servers.itervalues():
        for attr in changes:
            changed_attrs.add(attr)
    return query(object_id=filters.Any(*changed_servers.keys())).restrict(
            *changed_attrs).get_raw_data()

def _get_attr_regexps(stype_attrs):
    stype_attr_regexps = {}
    for stype_attr in ServerTypeAttributes.objects.select_related():
        stype_name = stype_attr.servertype.name
        try:
            regexp = re.compile(stype_attr.regex)
        except re.error:
            regexp = None
        attr_regexps = stype_attr_regexps.setdefault(stype_name, {})
        attr_regexps[stype_attr.attrib.name] = regexp
    return stype_attr_regexps

def _get_attr_required(stype_attrs):
    stype_attr_required = {}
    for stype_attr in ServerTypeAttributes.objects.select_related():
        stype_name = stype_attr.servertype.name
        stype_attr_required = stype_attr_required.setdefault(stype_name, {})
        stype_attr_required[stype_attr.attrib.name] = stype_attr.required
    return stype_attr_required

def _validate_structure(changed_servers):
    # FIXME: Validation of the inner structure
    for server_id, changes in changed_servers.iteritems():
        for attr, change in changes.iteritems():
            if attr not in lookups.attr_names:
                raise ValueError('No such attribute')
            action = change['action']
            if action == 'update':
                if not all(x in change for x in ('old', 'new')):
                    raise ValueError('Invalid update change')
            elif action == 'new':
                if 'new' not in change:
                    raise ValueError('Invalid new change')
            elif action == 'delete':
                if 'old' not in change:
                    raise ValueError('Invalid delete change')
            elif action == 'multi':
                if not all(x in change for x in ('add', 'remove')):
                    raise ValueError('Invalid multi change')
                if not lookups.attr_names[attr].multi:
                    raise ValueError('Not a multi attribute')

def _validate_regexp(changed_servers, servers, stype_attrs):
    stype_attr_regexps = _get_attr_regexps(stype_attrs)
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        attr_regexps = stype_attr_regexps[server['servertype']]
        for attr, change in changes.iteritems():
            regexp = attr_regexps.get(attr, None)
            action = change['action']
            if action == 'update' or action == 'new':
                if regexp and not regexp.match(change['new']):
                        violations.append((server_id, attr))
            elif action == 'multi':
                for value in change['add']:
                    if regexp and not regexp.match(value):
                        violations.append((server_id, attr))
                        break

def _validate_required(changed_servers, servers, stype_attrs):
    stype_attr_required = _get_attr_required(stype_attrs)
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        attr_required = stype_attr_required[server['servertype']]
        for attr, change in changes.iteritems():
            if change['action'] == 'delete' and attr_required[attr]:
                violations.append((server_id, attr))
    return violations

def _validate_commit(changed_servers, servers):
    newer = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            action = change['action']
            if action == 'new':
                if attr in server:
                    newer.append((server_id, attr, server[attr]))
            elif action == 'update' or action == 'delete':
                try:
                    if server[attr] != change['old']:
                        newer.append((server_id, attr, server[attr]))
                except KeyError:
                    newer.append((server_id, attr, None))
    return newer
