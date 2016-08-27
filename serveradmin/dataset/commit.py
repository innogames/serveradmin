from collections import defaultdict
import json
from ipaddress import ip_address, ip_network

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from adminapi.utils.json import json_encode_extra
from serveradmin.dataset.typecast import typecast
from serveradmin.hooks.slots import HookSlot
from serveradmin.serverdb.models import (
    Attribute,
    ServerTableSpecial,
    ServertypeAttribute,
    Server,
    ServerHostnameAttribute,
    ChangeCommit,
    ChangeUpdate,
    ChangeDelete,
)


class Commit(object):
    """Context class for all commit hooks."""

    def __init__(self, commit, user):
        self.user = user

        if 'deleted' in commit:
            self.deleted_servers = commit['deleted']
            self._validate_deletes()
        else:
            self.deleted_servers = []

        if 'changes' in commit:
            self.changed_servers = commit['changes']
            self._decorate_changes()
            self._validate_changes()
            self._cast_changed_values()
            self._clean_changes()
        else:
            self.changed_servers = {}

        # TODO Only use Django objects
        self.servers = _fetch_servers(self.changed_servers)

        # If non-empty, the commit will go through the backend, but an error
        # will be shown on the client.
        self.warnings = []

    def _validate_deletes(self):
            if not (
                isinstance(self.deleted_servers, (list, set)) and
                all(isinstance(x, (int, long)) for x in self.deleted_servers)
            ):
                raise ValueError('Invalid deleted servers')

    def _decorate_changes(self):
        servers = {s.server_id: s for s in (
            Server.objects.select_for_update()
            .filter(server_id__in=self.changed_servers.keys())
        )}

        for server_id, changes in self.changed_servers.items():
            for attribute_id, change in changes.items():
                change['server'] = servers[server_id]
                change['attribute'] = Attribute.objects.get(pk=attribute_id)

    def _validate_changes(self):
        for changes in self.changed_servers.values():
            for change in changes.values():
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
                    if not change['attribute'].multi:
                        raise ValueError('Not a multi attribute')

    def _cast_changed_values(self):
        for changes in self.changed_servers.values():
            for change in changes.values():
                server = change['server']
                attribute = change['attribute']
                action = change['action']

                if action == 'new':
                    change['new'] = typecast(attribute, change['new'])
                elif action == 'update':
                    if attribute.pk == 'intern_ip':
                        if server.servertype.ip_addr_type == 'network':
                            change['new'] = ip_network(change['new'])
                            change['old'] = ip_network(change['old'])
                        else:
                            change['new'] = ip_address(change['new'])
                            change['old'] = ip_address(change['old'])
                    else:
                        change['new'] = typecast(attribute, change['new'])
                        change['old'] = typecast(attribute, change['old'])
                elif action == 'multi':
                    change['add'] = typecast(attribute, change['add'])
                    change['remove'] = typecast(attribute, change['remove'])
                elif action == 'delete':
                    change['old'] = typecast(attribute, change['old'])

    def _clean_changes(self):
        for server_id, changes in self.changed_servers.items():
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
                        for value in change['add'].intersection(
                            change['remove']
                        ):
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
                del self.changed_servers[server_id]

    def apply_changes(self):
        # Changes should be applied in order to prevent integrity errors.
        self._remove_attributes()
        if self.deleted_servers:
            self._delete_servers()
        self._set_attributes()

        # Re-fetch servers before invoking hook, otherwise the hook will
        # receive incomplete data.
        self.servers = _fetch_servers(self.changed_servers)
        try:
            on_server_attribute_changed.invoke(
                commit=self,
                servers=self.servers.values(),
                changes=self.changed_servers,
            )
        except CommitIncomplete as error:
            self.warnings.append('Commit hook failed: {}'.format(
                unicode(error)
            ))

    def _remove_attributes(self):
        for server_id, changes in self.changed_servers.iteritems():
            for key, change in changes.iteritems():
                server = change['server']
                attribute = change['attribute']
                action = change['action']

                if action == 'delete':
                    server.get_attributes(attribute).delete()
                elif action == 'multi' and change['remove']:
                    for server_attribute in server.get_attributes(attribute):
                        if server_attribute.get_value() in change['remove']:
                            server_attribute.delete()

    def _delete_servers(self):
        # We first have to delete all of the hostname attributes
        # to avoid integrity errors.  Other attributes will just go away
        # with the servers.
        (
            ServerHostnameAttribute.objects
            .filter(server_id__in=self.deleted_servers)
            .delete()
        )

        try:
            Server.objects.filter(server_id__in=self.deleted_servers).delete()
        except IntegrityError as error:
            raise CommitError(
                'Cannot delete servers because they are referenced by {0}'
                .format(', '.join(str(o) for o in error.protected_objects))
            )

        # We should ignore the changes to the deleted servers.
        for server_id in self.deleted_servers:
            if server_id in self.changed_servers:
                del self.changed_servers[server_id]

    def _set_attributes(self):
        for server_id, changes in self.changed_servers.iteritems():
            for key, change in changes.iteritems():
                server = change['server']
                attribute = change['attribute']
                action = change['action']

                if isinstance(attribute.special, ServerTableSpecial):
                    if action == 'new' or action == 'update':
                        setattr(server, attribute.special.field, change['new'])
                    elif action == 'delete':
                        setattr(server, attribute.special.field, None)

                elif action == 'new':
                    server.add_attribute(attribute, change['new'])

                elif action == 'update':
                    server.get_attributes(attribute).get().save_value(
                        change['new']
                    )

                elif action == 'multi':
                    for value in change['add']:
                        server.add_attribute(attribute, value)

            # Save the special attributes.
            server.full_clean()
            server.save()


class CommitError(ValidationError):
    pass


class CommitValidationFailed(CommitError):
    def __init__(self, message, violations=None):
        CommitError.__init__(self, message)
        if violations is None:
            violations = []

        self.violations = violations


class CommitNewerData(CommitError):
    def __init__(self, message, newer=None):
        CommitError.__init__(self, message)
        if newer is None:
            newer = []
        self.newer = newer


class CommitIncomplete(CommitError):
    """This is a skip-able error.  It indicates that a commit was
    successfully stored, but some hooks have failed.
    """
    pass


class _ServerAttributedChangedHook(HookSlot):
    """Specialized hook that filters based on changes attributes."""
    def connect(self, hookfn, attribute_id, servertypes=None, filter=None):
        if servertypes and not isinstance(servertypes, tuple):
            raise ValueError(
                'Servertypes filter must be tuple: {}'.format(servertypes)
            )

        def filtered_fn(servers, changes, **kwargs):
            filtered_servers = []
            for server in servers:
                if servertypes and server['servertype'] not in servertypes:
                    continue
                server_changes = changes[server.object_id]
                if attribute_id not in server_changes:
                    continue

                old = server_changes[attribute_id].get('old', None)
                new = server_changes[attribute_id].get('new', None)
                if filter and not filter(server, old, new):
                    continue
                filtered_servers.append(server)
            if not filtered_servers:
                return
            hookfn(servers=filtered_servers, changes=changes, **kwargs)
        filtered_fn.__name__ = hookfn.__name__
        return HookSlot.connect(self, filtered_fn)

on_server_attribute_changed = _ServerAttributedChangedHook(
    'commit_server_changed',
    servers=list,
    changes=dict,
    commit=Commit,
)


# TODO: Move to commit object?
def commit_changes(
    commit,
    skip_validation=False,
    force_changes=False,
    app=None,
    user=None,
):
    """Commit server changes to the database after validation

    :param commit: Dictionary with the keys 'deleted' and 'changes' containing
                   a list of deleted servers and a dictionary of the servers'
                   changes.
    """
    with transaction.atomic():
        commit = Commit(commit, user)

        if not commit.changed_servers and not commit.deleted_servers:
            return

        servertype_attributes = _get_servertype_attributes(commit.servers)

        # Attributes must be always validated
        violations_attribs = _validate_attributes(
            commit.changed_servers, commit.servers, servertype_attributes
        )

        if not skip_validation:
            violations_readonly = _validate_readonly(
                commit.changed_servers, commit.servers
            )
            violations_regexp = _validate_regexp(
                commit.changed_servers,
                commit.servers,
                servertype_attributes,
            )
            violations_required = _validate_required(
                commit.changed_servers, commit.servers, servertype_attributes
            )
            if (
                violations_attribs or violations_readonly or
                violations_regexp or violations_required
            ):
                error_message = _build_error_message(
                    violations_attribs,
                    violations_readonly,
                    violations_regexp,
                    violations_required,
                )
                raise CommitValidationFailed(
                    error_message,
                    violations_attribs +
                    violations_readonly +
                    violations_regexp +
                    violations_required,
                )

        if violations_attribs:
            error_message = _build_error_message(violations_attribs, [], [])
            raise CommitValidationFailed(error_message, violations_attribs)

        if not force_changes:
            newer = _validate_commit(commit.changed_servers, commit.servers)
            if newer:
                raise CommitNewerData('Newer data available', newer)

        commit.apply_changes()
        _log_changes(commit.deleted_servers, commit.changed_servers, app, user)

    if commit.warnings:
        warnings = '\n'.join(commit.warnings)
        raise CommitIncomplete(
            'Commit was written, but hooks failed:\n\n{}'.format(warnings)
        )


def _log_changes(deleted_servers, changed_servers, app, user):
    # Import here to break cyclic import
    from serveradmin.dataset import query, filters

    if deleted_servers:
        old_servers = list(query(object_id=filters.Any(*deleted_servers)))
    else:
        old_servers = []

    servers = query(
        object_id=filters.Any(*changed_servers.keys())
    ).restrict('hostname')

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
    changed_attrs = set(['servertype', 'hostname', 'intern_ip'])
    for changes in changed_servers.itervalues():
        for attr in changes:
            changed_attrs.add(attr)

    queryset = QuerySet({'object_id': Any(*changed_servers.keys())})
    queryset.restrict(*changed_attrs)

    return queryset.get_results()


def _get_servertype_attributes(servers):
    servertype_ids = {s['servertype'] for s in servers.values()}
    servertype_attributes = defaultdict(dict)
    for item in ServertypeAttribute.objects.all():
        if item.servertype.pk in servertype_ids:
            servertype_attributes[item.servertype.pk][item.attribute.pk] = item

    return servertype_attributes


def _validate_attributes(changed_servers, servers, servertype_attributes):
    special_attribute_ids = [a.pk for a in Attribute.specials]

    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        attributes = servertype_attributes[server['servertype']]

        for attribute_id, change in changes.iteritems():
            # If servertype is attempted to be changed, we immediately
            # error out.
            if attribute_id == 'servertype':
                raise CommitValidationFailed('Cannot change servertype', [])

            # We have no more checks for the special attributes.
            if attribute_id in special_attribute_ids:
                continue

            if (
                # No such attribute.
                attribute_id not in attributes or
                # Attributes related via another one, cannot be changed.
                attributes[attribute_id].related_via_attribute
            ):
                violations.append((server_id, attribute_id))
                violations.append((server_id, attribute_id))

    return violations


def _validate_readonly(changed_servers, servers):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            if Attribute.objects.get(pk=attr).readonly:
                if attr in server and server[attr] != '':
                    violations.append((server_id, attr))
    return violations


def _validate_regexp(changed_servers, servers, servertype_attributes):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            try:
                sa = servertype_attributes[server['servertype']][attr]
            except KeyError:
                continue

            if not sa.regexp:
                continue

            action = change['action']

            if action == 'update' or action == 'new':
                if not sa.regexp_match(change['new']):
                    violations.append((server_id, attr))
            elif action == 'multi':
                for value in change['add']:
                    if not sa.regexp_match(value):
                        violations.append((server_id, attr))
                        break
    return violations


def _validate_required(changed_servers, servers, servertype_attributes):
    violations = []
    for server_id, changes in changed_servers.iteritems():
        server = servers[server_id]
        for attr, change in changes.iteritems():
            try:
                sa = servertype_attributes[server['servertype']][attr]
            except KeyError:
                continue

            if change['action'] == 'delete' and sa.required:
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
                message.append('{0}: {1} (#affected: {2})'.format(
                        message_type, vattr, num_affected
                    ))

    return '. '.join(message)
