import json

from django.db import IntegrityError, transaction
from django.core.exceptions import PermissionDenied, ValidationError

from adminapi.utils.json import json_encode_extra
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


class Commit(object):
    """Context class for all commit hooks."""

    def __init__(self, commit):
        if 'deleted' in commit:
            self.deletions = commit['deleted']
            self._validate_deletes()
        else:
            self.deletions = []

        if 'changes' in commit:
            self.changes = commit['changes']
            self._decorate_changes()
            self._validate_changes()
            self._clean_changes()
        else:
            self.changes = {}

        self.servers_to_change = _fetch_servers(self.changes.keys())
        self.servers_to_delete = _fetch_servers(self.deletions)

        # If non-empty, the commit will go through the backend, but an error
        # will be shown on the client.
        self.warnings = []

    def _validate_deletes(self):
        if not (
            isinstance(self.deletions, (list, set)) and
            all(isinstance(x, int) for x in self.deletions)
        ):
            raise CommitError('Invalid servers to delete')

    def _decorate_changes(self):
        servers = {s.server_id: s for s in (
            Server.objects.select_for_update()
            .filter(server_id__in=self.changes.keys())
        )}
        for server_id, changes in self.changes.items():
            for attribute_id, change in changes.items():
                change['server'] = servers[server_id]
                change['attribute'] = Attribute.objects.get(pk=attribute_id)

    def _validate_changes(self):    # NOQA: C901
        for changes in self.changes.values():
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

    def _clean_changes(self):   # NOQA: C901
        for server_id, changes in tuple(self.changes.items()):
            server_changed = False
            for attr, change in tuple(changes.items()):
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
                        if change['add'] or change['remove']:
                            server_changed = True
                        else:
                            del changes[attr]
                    else:
                        del changes[attr]
                elif action == 'delete':
                    server_changed = True
            if not server_changed:
                del self.changes[server_id]

    def apply_changes(self):
        # Changes should be applied in order to prevent integrity errors.
        self._delete_attributes()
        self._delete_servers()
        self._update_servers()
        self._upsert_attributes()

        # Re-fetch servers before invoking hook, otherwise the hook will
        # receive incomplete data.
        self.servers_to_change = _fetch_servers(self.changes.keys())
        try:
            on_server_attribute_changed.invoke(
                commit=self,
                servers=list(self.servers_to_change.values()),
                changes=self.changes,
            )
        except CommitIncomplete as error:
            self.warnings.append(
                'Commit hook failed:\n{}'.format(' '.join(error.messages))
            )

    def _delete_attributes(self):
        # We first have to delete all of the hostname attributes
        # to avoid integrity errors.  Other attributes will just go away
        # with the servers.
        if self.deletions:
            (
                ServerHostnameAttribute.objects
                .filter(server_id__in=self.deletions)
                .delete()
            )

        for server_id, changes in self.changes.items():
            for key, change in changes.items():
                server = change['server']
                attribute = change['attribute']
                action = change['action']

                if action == 'delete' or (
                    action == 'update' and change['new'] is None
                ):
                    server.get_attributes(attribute).delete()
                elif action == 'multi' and change['remove']:
                    for server_attribute in server.get_attributes(attribute):
                        if server_attribute.get_value() in change['remove']:
                            server_attribute.delete()

    def _delete_servers(self):
        if not self.deletions:
            return

        try:
            Server.objects.filter(server_id__in=self.deletions).delete()
        except IntegrityError as error:
            raise CommitError(
                'Cannot delete servers because they are referenced by {0}'
                .format(', '.join(str(o) for o in error.protected_objects))
            )

        # We should ignore the changes to the deleted servers.
        for server_id in self.deletions:
            if server_id in self.changes:
                del self.changes[server_id]

    def _update_servers(self):
        changed = set()
        for server_id, changes in self.changes.items():
            for change in changes.values():
                attribute = change['attribute']
                if not attribute.special:
                    continue
                assert change['action'] in ('new', 'update', 'multi')
                server = change['server']
                setattr(server, attribute.special.field, change.get('new'))
                changed.add(server)
        for server in changed:
            server.full_clean()
            server.save()

    def _upsert_attributes(self):
        for server_id, changes in self.changes.items():
            for change in changes.values():
                server = change['server']
                attribute = change['attribute']
                action = change['action']

                if attribute.special:
                    continue

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
    if not commit['changes'] and not commit['deleted']:
        return

    if not user:
        user = app.owner

    with transaction.atomic():
        commit = Commit(commit)

        access_control('edit', commit.servers_to_change, user, app)
        access_control('delete', commit.servers_to_delete, user, app)

        servertype_attributes = _get_servertype_attributes(
            commit.servers_to_change
        )

        # Attributes must be always validated
        violations_attribs = _validate_attributes(
            commit.changes, commit.servers_to_change, servertype_attributes
        )

        if not skip_validation:
            violations_readonly = _validate_readonly(
                commit.changes, commit.servers_to_change
            )
            violations_regexp = list(_validate_regexp(
                commit.changes,
                commit.servers_to_change,
                servertype_attributes,
            ))
            violations_required = _validate_required(
                commit.changes, commit.servers_to_change, servertype_attributes
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
            newer = _validate_commit(commit.changes, commit.servers_to_change)
            if newer:
                raise CommitNewerData('Newer data available', newer)

        _log_changes(commit.servers_to_delete, commit.changes, user, app)
        commit.apply_changes()
        access_control('commit', commit.servers_to_change, user, app)

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


def _log_changes(servers_to_delete, changes, user, app):
    if not (changes or servers_to_delete):
        return

    commit = ChangeCommit.objects.create(app=app, user=user)
    for server_id, updates in changes.items():
        ChangeUpdate.objects.create(
            commit=commit,
            server_id=server_id,
            updates_json=json.dumps(updates, default=json_encode_extra),
        )
    for attributes in servers_to_delete.values():
        attributes_json = json.dumps(attributes, default=json_encode_extra)
        ChangeDelete.objects.create(
            commit=commit,
            server_id=attributes['object_id'],
            attributes_json=attributes_json,
        )


def _fetch_servers(server_ids):
    # Import here to break cyclic import
    from serveradmin.dataset.queryset import QuerySet
    from serveradmin.dataset.filters import Any

    queryset = QuerySet({'object_id': Any(*server_ids)})

    return {s.object_id: s for s in queryset.get_results()}


def _get_servertype_attributes(servers):
    servertype_attributes = dict()
    for servertype_id in {s['servertype'] for s in servers.values()}:
        servertype_attributes[servertype_id] = dict()
        for sa in Servertype.objects.get(pk=servertype_id).attributes.all():
            servertype_attributes[servertype_id][sa.attribute.pk] = sa

    return servertype_attributes


def _validate_attributes(changes, servers, servertype_attributes):
    violations = []
    for server_id, attribute_changes in changes.items():
        server = servers[server_id]
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
                violations.append((server_id, attribute_id))
                violations.append((server_id, attribute_id))

    return violations


def _validate_readonly(changes, servers):
    violations = []
    for server_id, attribute_changes in changes.items():
        server = servers[server_id]
        for attr, change in attribute_changes.items():
            if Attribute.objects.get(pk=attr).readonly:
                if attr in server and server[attr] != '':
                    violations.append((server_id, attr))
    return violations


def _validate_regexp(changes, servers, servertype_attributes):
    for server_id, attribute_changes in changes.items():
        server = servers[server_id]
        for attribute_id, change in attribute_changes.items():
            sa = servertype_attributes[server['servertype']].get(attribute_id)
            if not sa or not sa.regexp:
                continue

            action = change['action']
            if action == 'update' or action == 'new':
                if change['new'] is None:
                    continue
                if not sa.regexp_match(change['new']):
                    yield server_id, attribute_id
            elif action == 'multi':
                for value in change['add']:
                    if not sa.regexp_match(value):
                        yield server_id, attribute_id
                        break


def _validate_required(changes, servers, servertype_attributes):
    violations = []
    for server_id, attribute_changes in changes.items():
        server = servers[server_id]
        for attribute_id, change in attribute_changes.items():
            attribute = Attribute.objects.get(pk=attribute_id)
            if attribute.special:
                continue

            sa = servertype_attributes[server['servertype']][attribute_id]
            if change['action'] == 'delete' and sa.required:
                violations.append((server_id, attribute_id))
    return violations


def _validate_commit(changes, servers):
    newer = []
    for server_id, attribute_changes in changes.items():
        server = servers[server_id]
        for attr, change in attribute_changes.items():
            action = change['action']
            if action == 'new':
                if attr in server:
                    newer.append((server_id, attr, server[attr]))
            elif action == 'update' or action == 'delete':
                try:
                    if str(server[attr]) != str(change['old']):
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
            for vattr, num_affected in seen.items():
                message.append('{0}: {1} (#affected: {2})'.format(
                    message_type, vattr, num_affected
                ))

    return '. '.join(message)
