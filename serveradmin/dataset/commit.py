import time
import json

from adminapi.dataset.exceptions import CommitValidationFailed, CommitNewerData
from adminapi.utils.json import json_encode_extra
from serveradmin.dataset.base import lookups, ServerTableSpecial
from serveradmin.dataset.typecast import typecast
from serveradmin.serverdb.models import (
    ServerObject,
    ChangeCommit,
    ChangeUpdate,
    ChangeDelete,
)

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
        ServerObject.objects.filter(server_id__in=deleted_servers).delete()
    _apply_changes(changed_servers)

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
        for key, change in changes.iteritems():
            attribute = lookups.attr_names[key]
            action = change['action']

            if action == 'new':
                change['new'] = typecast(attribute, change['new'])
            elif action == 'update':
                change['new'] = typecast(attribute, change['new'])
                change['old'] = typecast(attribute, change['old'])
            elif action == 'multi':
                change['add'] = typecast(attribute, change['add'])
                change['remove'] = typecast(attribute, change['remove'])
            elif action == 'delete':
                change['old'] = typecast(attribute, change['old'])

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

def _apply_changes(changed_servers):

    queryset = ServerObject.objects.select_for_update()
    queryset = queryset.filter(server_id__in=changed_servers.keys())
    servers = {s.server_id: s for s in queryset}

    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]

        for key, change in changes.iteritems():
            attribute = lookups.attr_names[key]
            action = change['action']

            if isinstance(attribute.special, ServerTableSpecial):
                if action == 'new' or action == 'update':
                    setattr(server, attribute.special.field, change['new'])
                elif action == 'delete':
                    setattr(server, attribute.special.field, None)

            elif action == 'new':
                server.add_attribute_value(attribute, change['new'])

            elif action == 'update':
                attribute_value = server.attributevalue_set.get(attrib=attribute)
                attribute_value.reset(change['new'])
                attribute_value.save()

            elif action == 'delete':
                server.attributevalue_set.filter(attrib=attribute).delete()

            elif action == 'multi':

                if change['remove']:
                    server.attributevalue_set.filter(
                        attrib=attribute,
                        value__in=(
                            attribute.serialize_value(value)
                            for value in change['remove']
                        ),
                    ).delete()

                for value in change['add']:
                    server.add_attribute_value(attribute, value)

        server.save()

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
