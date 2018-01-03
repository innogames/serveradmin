import json

from django.db import IntegrityError, transaction
from django.core.exceptions import PermissionDenied, ValidationError

from adminapi.request import json_encode_extra
from serveradmin.hooks.slots import HookSlot
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    Server,
    ServerAttribute,
    ServerHostnameAttribute,
    ChangeCommit,
    ChangeUpdate,
    ChangeDelete,
)
from serveradmin.serverdb.query_materializer import QueryMaterializer


class Commit(object):
    """Context class for all commit hooks."""

    def __init__(self, commit):
        if 'deleted' in commit:
            self.deleted = commit['deleted']
            self._servers_to_delete = {
                s.server_id: s for s in (
                    Server.objects.select_for_update()
                    .filter(server_id__in=self.deleted)
                )
            }
        else:
            self.deleted = []
            self._servers_to_delete = {}

        if 'changes' in commit:
            self.changed = commit['changed']
            self._servers_to_change = {
                s.server_id: s for s in (
                    Server.objects.select_for_update()
                    .filter(server_id__in=[
                        c['object_id'] for c in self.changed
                    ])
                )
            }
        else:
            self.changed = []
            self._servers_to_change = {}

        self._objects_to_change = _materialize_servers(self._servers_to_change)
        self._objects_to_delete = _materialize_servers(self._servers_to_delete)

        # If non-empty, the commit will go through the backend, but an error
        # will be shown on the client.
        self.warnings = []

    def apply_changes(self):
        # Changes should be applied in order to prevent integrity errors.
        self._delete_attributes()
        self._delete_servers()
        self._update_servers()
        self._upsert_attributes()

        # Re-fetch servers before invoking hook, otherwise the hook will
        # receive incomplete data.
        self._objects_to_change = _materialize_servers(self._servers_to_change)
        try:
            on_server_attribute_changed.invoke(
                commit=self,
                servers=list(self._objects_to_change.values()),
                changed=self.changed,
            )
        except CommitIncomplete as error:
            self.warnings.append(
                'Commit hook failed:\n{}'.format(' '.join(error.messages))
            )

    def _delete_attributes(self):
        # We first have to delete all of the hostname attributes
        # to avoid integrity errors.  Other attributes will just go away
        # with the servers.
        if self.deleted:
            (
                ServerHostnameAttribute.objects
                .filter(server_id__in=self.deleted)
                .delete()
            )

        for changes in self.changed:
            object_id = changes['object_id']

            for attribute_id, change in changes.items():
                if attribute_id == 'object_id':
                    continue

                server = self._servers_to_change[object_id]
                attribute = Attribute.objects.get(pk=attribute_id)
                action = change['action']

                if action == 'delete' or (
                    action == 'update' and change['new'] is None
                ):
                    server.get_attributes(attribute).delete()
                elif action == 'multi' and change['remove']:
                    for server_attribute in server.get_attributes(attribute):
                        value = server_attribute.get_value()
                        if isinstance(value, Server):
                            value = value.hostname
                        if value in change['remove']:
                            server_attribute.delete()

    def _delete_servers(self):
        if not self.deleted:
            return

        try:
            for server in self._servers_to_delete.values():
                server.delete()
        except IntegrityError as error:
            raise CommitError(
                'Cannot delete servers because they are referenced by {0}'
                .format(', '.join(str(o) for o in error.protected_objects))
            )

        # We should ignore the changes to the deleted servers.
        for server_id in self.deleted:
            if server_id in self.changed:
                del self.changes[server_id]

    def _update_servers(self):
        changed = set()
        for changes in self.changed:
            object_id = changes['object_id']

            for attribute_id, change in changes.items():
                if attribute_id == 'object_id':
                    continue

                attribute = Attribute.objects.get(pk=attribute_id)
                if not attribute.special:
                    continue

                assert change['action'] in ('new', 'update', 'multi')
                server = self._servers_to_change[object_id]
                setattr(server, attribute.special.field, change.get('new'))
                changed.add(server)

        for server in changed:
            server.full_clean()
            server.save()

    def _upsert_attributes(self):
        for changes in self.changed:
            object_id = changes['object_id']

            for attribute_id, change in changes.items():
                attribute = Attribute.objects.get(pk=attribute_id)
                if attribute.special:
                    continue

                server = self._servers_to_change[object_id]

                action = change['action']
                if action == 'multi':
                    for value in change['add']:
                        server.add_attribute(attribute, value)
                    continue
                if action not in ('new', 'update'):
                    continue
                if change['new'] is None:
                    continue

                try:
                    server_attribute = server.get_attributes(attribute).get()
                except ServerAttribute.get_model(attribute.type).DoesNotExist:
                    server.add_attribute(attribute, change['new'])
                else:
                    server_attribute.save_value(change['new'])


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
    """Specialized hook that filters based on changed attributes."""
    def connect(self, hookfn, attribute_id, servertypes=None, filter=None):
        if servertypes and not isinstance(servertypes, tuple):
            raise ValueError(
                'Servertypes filter must be tuple: {}'.format(servertypes)
            )

        def filtered_fn(servers, changed, **kwargs):
            changes = {c['object_id'] for c in changed}
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
    'commit_server_changed', servers=list, changed=list, commit=Commit
)


# TODO: Move to commit object?
def commit_changes(commit, app=None, user=None):
    """Commit server changes to the database after validation

    :param commit: Dictionary with the keys 'deleted' and 'changes' containing
                   a list of deleted servers and a dictionary of the servers'
                   changes.
    """
    if not commit['changed'] and not commit['deleted']:
        return

    if not user:
        user = app.owner

    with transaction.atomic():
        commit = Commit(commit)

        access_control('edit', commit._objects_to_change, user, app)
        access_control('delete', commit._objects_to_delete, user, app)

        servertype_attributes = _get_servertype_attributes(
            commit._objects_to_change
        )

        # Attributes must be always validated
        violations_attribs = _validate_attributes(
            commit.changed, commit._objects_to_change, servertype_attributes
        )
        violations_readonly = _validate_readonly(
            commit.changed, commit._objects_to_change
        )
        violations_regexp = list(_validate_regexp(
            commit.changed,
            commit._objects_to_change,
            servertype_attributes,
        ))
        violations_required = _validate_required(
            commit.changed,
            commit._objects_to_change,
            servertype_attributes,
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

        newer = _validate_commit(commit.changed, commit._objects_to_change)
        if newer:
            raise CommitNewerData('Newer data available', newer)

        _log_changes(commit._objects_to_delete, commit.changed, user, app)
        commit.apply_changes()
        access_control('commit', commit._objects_to_change, user, app)

    if commit.warnings:
        warnings = '\n'.join(commit.warnings)
        raise CommitIncomplete(
            'Commit was written, but hooks failed:\n\n{}'.format(warnings)
        )


def access_control(action, servers, user, app):
    entities = list()
    if not user.is_superuser:
        entities.append((
            'user',
            user,
            list(user.access_control_groups.all()),
        ))
    if app and not app.superuser:
        entities.append((
            'application',
            app,
            list(app.access_control_groups.all()),
        ))

    for server in servers.values():
        matched_groups = set()
        for entity_class, entity_name, entity_groups in entities:
            for group in entity_groups:
                if group in matched_groups:
                    break
                if group.match_server(action, server):
                    matched_groups.add(group)
                    break
            else:
                raise PermissionDenied(
                    'Insufficient access rights on {} of server "{}" '
                    'for {} "{}"'
                    .format(
                        action, server['hostname'], entity_class, entity_name
                    )
                )


def _log_changes(_objects_to_delete, changes, user, app):
    if not (changes or _objects_to_delete):
        return

    commit = ChangeCommit.objects.create(app=app, user=user)
    for updates in changes:
        ChangeUpdate.objects.create(
            commit=commit,
            server_id=updates['object_id'],
            updates_json=json.dumps(updates, default=json_encode_extra),
        )
    for attributes in _objects_to_delete.values():
        attributes_json = json.dumps(attributes, default=json_encode_extra)
        ChangeDelete.objects.create(
            commit=commit,
            server_id=attributes['object_id'],
            attributes_json=attributes_json,
        )


def _materialize_servers(servers):
    return {
        o['object_id']: o
        for o in QueryMaterializer(servers.values(), None)
    }


def _get_servertype_attributes(servers):
    servertype_attributes = dict()
    for servertype_id in {s['servertype'] for s in servers.values()}:
        servertype_attributes[servertype_id] = dict()
        for sa in Servertype.objects.get(pk=servertype_id).attributes.all():
            servertype_attributes[servertype_id][sa.attribute.pk] = sa

    return servertype_attributes


def _validate_attributes(changes, servers, servertype_attributes):
    violations = []
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        attributes = servertype_attributes[server['servertype']]

        for attribute_id, change in attribute_changes.items():
            # If servertype is attempted to be changed, we immediately
            # error out.
            if attribute_id == 'servertype':
                raise CommitValidationFailed('Cannot change servertype', [])

            # We have no more checks for the special attributes.
            if attribute_id in Attribute.specials:
                continue

            if (
                # No such attribute.
                attribute_id not in attributes or
                # Attributes related via another one, cannot be changed.
                attributes[attribute_id].related_via_attribute
            ):
                violations.append((object_id, attribute_id))
                violations.append((object_id, attribute_id))

    return violations


def _validate_readonly(changes, servers):
    violations = []
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        for attr, change in attribute_changes.items():
            if Attribute.objects.get(pk=attr).readonly:
                if attr in server and server[attr] != '':
                    violations.append((object_id, attr))
    return violations


def _validate_regexp(changes, servers, servertype_attributes):
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        for attribute_id, change in attribute_changes.items():
            sa = servertype_attributes[server['servertype']].get(attribute_id)
            if not sa or not sa.regexp:
                continue

            action = change['action']
            if action == 'update' or action == 'new':
                if change['new'] is None:
                    continue
                if not sa.regexp_match(change['new']):
                    yield object_id, attribute_id
            elif action == 'multi':
                for value in change['add']:
                    if not sa.regexp_match(value):
                        yield object_id, attribute_id
                        break


def _validate_required(changes, servers, servertype_attributes):
    violations = []
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        for attribute_id, change in attribute_changes.items():
            attribute = Attribute.objects.get(pk=attribute_id)
            if attribute.special:
                continue

            sa = servertype_attributes[server['servertype']][attribute_id]
            if change['action'] == 'delete' and sa.required:
                violations.append((object_id, attribute_id))
    return violations


def _validate_commit(changes, servers):
    newer = []
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        for attr, change in attribute_changes.items():
            if attr == 'object_id':
                continue

            action = change['action']
            if action == 'new':
                if attr in server:
                    newer.append((object_id, attr, server[attr]))
            elif action == 'update' or action == 'delete':
                try:
                    if str(server[attr]) != str(change['old']):
                        newer.append((object_id, attr, server[attr]))
                except KeyError:
                    newer.append((object_id, attr, None))

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
            for vattr, num_affected in seen.items():
                message.append('{0}: {1} (#affected: {2})'.format(
                    message_type, vattr, num_affected
                ))

    return '. '.join(message)
