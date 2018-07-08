"""Serveradmin - Query Committer

Copyright (c) 2018 InnoGames GmbH
"""

import json
from itertools import chain

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.dispatch.dispatcher import Signal

from adminapi.dataset import DatasetCommit
from adminapi.request import json_encode_extra
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    Server,
    ServerAttribute,
    ServerRelationAttribute,
    ChangeAdd,
    ChangeCommit,
    ChangeUpdate,
    ChangeDelete,
)
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)

pre_commit = Signal()


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


def commit_query(created=[], changed=[], deleted=[], app=None, user=None):
    """The main function to commit queries"""

    if not user:
        user = app.owner

    pre_commit.send_robust(
        commit_query, created=created, changed=changed, deleted=deleted
    )

    entities = []
    if not user.is_superuser:
        entities.append(
            ('user', user, list(user.access_control_groups.all()))
        )
    if app and not app.superuser:
        entities.append(
            ('application', app, list(app.access_control_groups.all()))
        )

    # TODO: Find out which attributes we actually need
    attribute_lookup = {
        a.pk: a for a in Attribute.objects.all() if not a.special
    }
    joined_attributes = {
        a: None
        for a
        in list(attribute_lookup.values()) + list(Attribute.specials.values())
    }

    with transaction.atomic():
        change_commit = ChangeCommit.objects.create(app=app, user=user)
        changed_servers = _fetch_servers(set(c['object_id'] for c in changed))
        changed_objects = _materialize(changed_servers, joined_attributes)

        deleted_servers = _fetch_servers(deleted)
        deleted_objects = _materialize(deleted_servers, joined_attributes)
        _validate(attribute_lookup, changed, changed_objects)

        # Changes should be applied in order to prevent integrity errors.
        _delete_attributes(attribute_lookup, changed, changed_servers, deleted)
        _delete_servers(changed, deleted, deleted_servers)
        created_servers = _create_servers(attribute_lookup, created)
        created_objects = _materialize(created_servers, joined_attributes)
        _update_servers(changed, changed_servers)
        _upsert_attributes(attribute_lookup, changed, changed_servers)
        changed_objects = _materialize(changed_servers, joined_attributes)

        _access_control(
            entities, created_objects, changed_objects, deleted_objects
        )
        _log_changes(change_commit, changed, created_objects, deleted_objects)

    return DatasetCommit(
        list(created_objects.values()),
        list(changed_objects.values()),
        list(deleted_objects.values()),
    )


def _validate(attribute_lookup, changed, changed_objects):
    servertype_attributes = _get_servertype_attributes(changed_objects)

    # Attributes must be always validated
    violations_attribs = _validate_attributes(
        changed, changed_objects, servertype_attributes
    )
    violations_readonly = _validate_readonly(
        attribute_lookup, changed, changed_objects
    )
    violations_regexp = list(
        _validate_regexp(changed, changed_objects, servertype_attributes)
    )
    violations_required = _validate_required(
        changed, changed_objects, servertype_attributes
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

    newer = _validate_commit(changed, changed_objects)
    if newer:
        raise CommitNewerData('Newer data available', newer)


def _delete_attributes(attribute_lookup, changed, changed_servers, deleted):
    # We first have to delete all of the relation attributes
    # to avoid integrity errors.  Other attributes will just go away
    # with the servers.
    if deleted:
        (
            ServerRelationAttribute.objects
            .filter(server_id__in=deleted)
            .delete()
        )

    for changes in changed:
        object_id = changes['object_id']

        for attribute_id, change in changes.items():
            if attribute_id in Attribute.specials:
                continue

            server = changed_servers[object_id]
            attribute = attribute_lookup[attribute_id]
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


def _delete_servers(changed, deleted, deleted_servers):
    if not deleted:
        return

    try:
        for server in deleted_servers.values():
            server.delete()
    except IntegrityError as error:
        raise CommitError(
            'Cannot delete servers because they are referenced by {0}'
            .format(', '.join(str(o) for o in error.protected_objects))
        )

    # We should ignore the changes to the deleted servers.
    for server_id in deleted:
        if server_id in changed:
            del changed[server_id]


def _create_servers(attribute_lookup, created):
    created_servers = {}
    for attributes in created:
        if 'hostname' not in attributes:
            raise CommitError('"hostname" attribute is required.')
        hostname = attributes['hostname']

        if 'servertype' not in attributes:
            raise CommitError('"servertype" attribute is required.')
        servertype = _get_servertype(attributes)

        if 'intern_ip' not in attributes:
            raise CommitError('"intern_ip" attribute is required.')
        intern_ip = attributes['intern_ip']

        attributes = dict(_get_real_attributes(attributes, attribute_lookup))
        _validate_real_attributes(servertype, attributes)

        server = _insert_server(hostname, intern_ip, servertype, attributes)

        created_server = {k.pk: v for k, v in attributes.items()}
        created_server['hostname'] = hostname
        created_server['servertype'] = servertype.pk
        created_server['intern_ip'] = intern_ip

        created_servers[server.server_id] = server

    return created_servers


def _update_servers(changed, changed_servers):
    really_changed = set()
    for changes in changed:
        object_id = changes['object_id']

        for attribute_id, change in changes.items():
            if attribute_id == 'object_id':
                continue

            if attribute_id not in Attribute.specials:
                continue

            assert change['action'] in ('new', 'update', 'multi')
            server = changed_servers[object_id]
            attribute = Attribute.specials[attribute_id]
            setattr(server, attribute.special.field, change.get('new'))
            really_changed.add(server)

    for server in really_changed:
        server.full_clean()
        server.save()


def _upsert_attributes(attribute_lookup, changed, changed_servers):
    for changes in changed:
        object_id = changes['object_id']

        for attribute_id, change in changes.items():
            if attribute_id in Attribute.specials:
                continue

            attribute = attribute_lookup[attribute_id]
            server = changed_servers[object_id]

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


def _access_control(
    entities, created_objects, changed_objects, deleted_objects
):
    for server in chain(
        created_objects.values(),
        changed_objects.values(),
        deleted_objects.values(),
    ):
        for entity_class, entity_name, groups in entities:
            if not any(
                _can_access_server(changed_objects, server, g) for g in groups
            ):
                raise PermissionDenied(
                    'Insufficient access rights to server "{}" for {} "{}"'
                    .format(server['hostname'], entity_class, entity_name)
                )


def _can_access_server(changed_objects, new_object, acl):
    if not all(
        f.matches(new_object.get(a))
        for a, f in acl.get_filters().items()
    ):
        return False

    if new_object['object_id'] in changed_objects:
        old_object = changed_objects[new_object['object_id']]
    else:
        old_object = get_default_attribute_values(new_object['servertype'])

    attribute_ids = {a.pk for a in acl.attributes.all()}
    if not all(
        a in attribute_ids or v == old_object[a]
        for a, v in new_object.items()
    ):
        return False

    return True


def _log_changes(commit, changed, created_objects, deleted_objects):
    for updates in changed:
        ChangeUpdate.objects.create(
            commit=commit,
            server_id=updates['object_id'],
            updates_json=json.dumps(updates, default=json_encode_extra),
        )

    for attributes in deleted_objects.values():
        attributes_json = json.dumps(attributes, default=json_encode_extra)
        ChangeDelete.objects.create(
            commit=commit,
            server_id=attributes['object_id'],
            attributes_json=attributes_json,
        )

    for obj in created_objects.values():
        attributes_json = json.dumps(
            obj, default=json_encode_extra
        )
        ChangeAdd.objects.create(
            commit=commit,
            server_id=obj['object_id'],
            attributes_json=attributes_json,
        )


def _fetch_servers(object_ids):
    servers = {
        s.server_id: s
        for s
        in Server.objects.select_for_update().filter(server_id__in=object_ids)
    }
    for object_id in object_ids:
        if object_id in servers:
            continue
        raise CommitError('Cannot find object with id {}'.format(object_id))

    return servers


def _materialize(servers, joined_attributes):
    return {
        o['object_id']: o
        for o in QueryMaterializer(list(servers.values()), joined_attributes)
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


def _validate_readonly(attribute_lookup, changes, servers):
    violations = []
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        server = servers[object_id]
        for attr, change in attribute_changes.items():
            if attr in Attribute.specials:
                continue

            if attribute_lookup[attr].readonly:
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
            if attribute_id in Attribute.specials:
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


def _get_servertype(attributes):
    try:
        return Servertype.objects.get(pk=attributes['servertype'])
    except Servertype.DoesNotExist:
        raise CommitError('Unknown servertype: ' + attributes['servertype'])


def _get_real_attributes(attributes, attribute_lookup):
    for attribute_id, value in attributes.items():
        if attribute_id in Attribute.specials:
            continue

        attribute = attribute_lookup[attribute_id]
        value_multi = (
            isinstance(value, (list, set)) or
            hasattr(value, '_proxied_set')
        )

        if attribute.multi and not value_multi:
            raise CommitError(
                '{0} is a multi attribute, but {1} of type {2} given.'
                .format(attribute, repr(value), type(value).__name__)
            )
        if not attribute.multi and value_multi:
            raise CommitError(
                '{0} is not a multi attribute, but {1} of type {2} given.'
                .format(attribute, repr(value), type(value).__name__)
            )

        # Ignore nulls
        if not value_multi and value is None:
            continue

        # Ignore the virtual attribute types
        if attribute.type in ['reverse', 'supernet']:
            continue

        yield attribute, value


def _validate_real_attributes(servertype, real_attributes):     # NOQA: C901
    violations_regexp = []
    violations_required = []
    servertype_attributes = set()
    for sa in servertype.attributes.all():
        attribute = sa.attribute
        servertype_attributes.add(attribute)

        # Ignore the related via attributes
        if sa.related_via_attribute:
            if sa.attribute in real_attributes:
                del real_attributes[attribute]
            continue

        # Handle not existing attributes (fill defaults, validate require)
        if attribute not in real_attributes:
            if attribute.multi:
                real_attributes[attribute] = sa.get_default_value()
            elif sa.required:
                if sa.default_value is not None:
                    real_attributes[attribute] = sa.get_default_value()
                else:
                    violations_required.append(attribute.pk)
                    continue
            else:
                if sa.default_value is not None:
                    real_attributes[attribute] = sa.get_default_value()
                else:
                    continue

        value = real_attributes[attribute]

        if attribute.multi:
            if sa.regexp:
                for val in value:
                    if not sa.regexp_match(str(val)):
                        violations_regexp.append(attribute.pk)
        elif sa.regexp:
            if not sa.regexp_match(value):
                violations_regexp.append(attribute.pk)

    # Check for attributes that are not defined on this servertype
    violations_attribs = []
    for attr in real_attributes:
        if attr not in servertype_attributes:
            violations_attribs.append(str(attr))

    handle_violations(
        violations_regexp,
        violations_required,
        violations_attribs,
    )


def _insert_server(hostname, intern_ip, servertype, attributes):

    if Server.objects.filter(hostname=hostname).exists():
        raise CommitError('Server with that hostname already exists')

    server = Server.objects.create(
        hostname=hostname,
        intern_ip=intern_ip,
        _servertype=servertype,
    )
    server.full_clean()
    server.save()

    for attribute, value in attributes.items():
        if attribute.multi:
            for single_value in value:
                server.add_attribute(attribute, single_value)
        else:
            server.add_attribute(attribute, value)

    return server


def handle_violations(
    violations_regexp,
    violations_required,
    violations_attribs,
):
    if violations_regexp or violations_required:
        if violations_regexp:
            regexp_msg = 'Attributes violating regexp: {0}. '.format(
                ', '.join(violations_regexp)
            )
        else:
            regexp_msg = ''
        if violations_required:
            required_msg = 'Attributes violating required: {0}.'.format(
                ', '.join(violations_required)
            )
        else:
            required_msg = ''

        raise CommitError(
            'Validation failed. {0}{1}'.format(regexp_msg, required_msg),
            violations_regexp + violations_required,
        )
    if violations_attribs:
        raise CommitError(
            'Attributes {0} are not defined on '
            'this servertype. You can\'t skip this validation!'
            .format(', '.join(violations_attribs)),
            violations_regexp + violations_required + violations_attribs,
        )
