"""Serveradmin - Query Committer

Copyright (c) 2023 InnoGames GmbH
"""

import logging
from itertools import chain
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from adminapi.dataset import DatasetCommit
from adminapi.request import json_encode_extra
from serveradmin.apps.models import Application
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    Server,
    ServerAttribute,
    ServerRelationAttribute,
    ChangeCommit,
    Change,
    ServertypeAttribute,
)
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)
from serveradmin.serverdb.signals import pre_commit, post_commit

logger = logging.getLogger(__name__)


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

    pre_commit.send_robust(commit_query, created=created, changed=changed, deleted=deleted)

    # TODO: Find out which attributes we actually need
    attribute_lookup = {a.pk: a for a in Attribute.objects.all()}
    joined_attributes = {a: None for a in list(attribute_lookup.values()) + list(Attribute.specials.values())}

    # TODO: We rely on the "protocol" that everything that creates or changes
    #       one or more Server(s) uses this API or also acquires an exclusive
    #       lock as happening below in _fetch_servers.
    #
    #       If not, "nonrepeatable reads" might happen since we fetch data for
    #       the same objects multiple times but have only the isolation level
    #       read committed.
    #
    #       We should check if we can make the commit_query more robust against
    #       changes elsewhere by changing to the isolation level
    #       # "repeatable read".
    with transaction.atomic():
        changed_servers = _fetch_servers(set(c['object_id'] for c in changed))
        unchanged_objects = _materialize(changed_servers, joined_attributes)

        deleted_servers = _fetch_servers(deleted)
        deleted_objects = _materialize(deleted_servers, joined_attributes)
        # TODO: Refactor validation
        #
        # This methods calls a set of functions to validate if changes to
        # objects are valid. Additionally there is some extra validation in
        # in _create_servers. Parts of this validation is shared and currently
        # missing in the _create_servers validation (e.g. setting values for
        # read-only attributes).
        #
        # We should refactor and fix this. Maybe we can use the standard forms
        # API here by implementing some custom validators and building forms
        # for the servertypes on-the-fly as described here:
        #
        #   - https://docs.djangoproject.com/en/2.2/ref/forms/validation/
        #
        # This would allow us to work with Django board tools and all it's
        # features. Less pain because we always work around or even clash
        # with the Django work flow and last but least allow us to use the
        # same logic/code for the Servershell (edit, new) page and the Query
        # engine (Web API) which currently does not use forms at all.
        _validate(attribute_lookup, changed, unchanged_objects)

        # Changes should be applied in order to prevent integrity errors.
        _delete_attributes(attribute_lookup, changed, changed_servers, deleted)
        _delete_servers(changed, deleted, deleted_servers)
        created_servers = _create_servers(attribute_lookup, created)
        created_objects = _materialize(created_servers, joined_attributes)
        _update_servers(changed, changed_servers)
        _upsert_attributes(attribute_lookup, changed, changed_servers)
        changed_objects = _materialize(changed_servers, joined_attributes)

        # TODO Improve this function by checking only attributes of ACLs that
        #      have actually changed and not all.
        _access_control(user, app, unchanged_objects, created_objects, changed_objects, deleted_objects)

        _log_changes(user, app, changed, created_objects, deleted_objects)

    post_commit.send_robust(commit_query, created=created, changed=changed, deleted=deleted)

    return DatasetCommit(
        list(created_objects.values()),
        list(changed_objects.values()),
        list(deleted_objects.values()),
    )


def _validate(attribute_lookup, changed, changed_objects):
    servertype_attributes = _get_servertype_attributes(changed_objects)

    # Attributes must be always validated
    violations_attribs = _validate_attributes(changed, changed_objects, servertype_attributes)
    violations_readonly = _validate_readonly(attribute_lookup, changed, changed_objects)
    violations_regexp = list(_validate_regexp(changed, changed_objects, attribute_lookup))
    violations_required = _validate_required(changed, changed_objects, servertype_attributes)
    if violations_attribs or violations_readonly or violations_regexp or violations_required:
        error_message = _build_error_message(
            violations_attribs,
            violations_readonly,
            violations_regexp,
            violations_required,
        )
        raise CommitValidationFailed(
            error_message,
            violations_attribs + violations_readonly + violations_regexp + violations_required,
        )

    newer = _validate_commit(changed, changed_objects)
    if newer:
        raise CommitNewerData('Newer data available', newer)


def _delete_attributes(attribute_lookup, changed, changed_servers, deleted):
    # We first have to delete all of the relation attributes
    # to avoid integrity errors.  Other attributes will just go away
    # with the servers.
    if deleted:
        (ServerRelationAttribute.objects.filter(server_id__in=deleted).delete())

    for changes in changed:
        object_id = changes['object_id']

        for attribute_id, change in changes.items():
            if attribute_id in Attribute.specials:
                continue

            server = changed_servers[object_id]
            attribute = attribute_lookup[attribute_id]
            action = change['action']

            if action == 'delete' or (action == 'update' and change['new'] is None):
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
            'Cannot delete servers because they are referenced by {0}'.format(
                ', '.join(str(o) for o in error.protected_objects)
            )
        )

    # We should ignore the changes to the deleted servers.
    for server_id in deleted:
        if server_id in changed:
            del changed[server_id]


def _create_servers(attribute_lookup, created):
    created_servers = {}
    for attributes in created:
        if not attributes.get('hostname'):
            raise CommitError('"hostname" attribute is required.')
        hostname = attributes['hostname']

        if not attributes.get('servertype'):
            raise CommitError('"servertype" attribute is required.')
        servertype = _get_servertype(attributes)

        intern_ip = attributes.get('intern_ip')

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
    user: Optional[User],
    app: Optional[Application],
    unchanged_objects: dict,
    created_objects: dict,
    changed_objects: dict,
    deleted_objects: dict,
) -> None:
    """Enforce serveradmin ACLs

    For Servershell commits, ensure the user is allowed to make the requested
    changes.  For adminapi commits, ensure both the app is allowed to make the
    requested changes.

    Serveradmin ACLs are additive. This means not all ACLs must allow all the
    changes a user or app is trying to make, but a single ACL is enough.

    Note: Different ACLs may be used to permit different parts of a commit.
    The commit is checked per object changed in the commit.  As a result at
    least all changes to a single object within a commit must be permissible
    via a single ACL.

    Note: when a user tries to make a change that is not permissible by any of
    its ACLs, the error message can become rather complex, listing all the
    reasons all the users ACLs were not applicable.

    Raises PermissionDenied if a change is not permissible.
    Returns None on success.
    """

    # superusers and apps can not violate permissions.
    if (user and user.is_superuser) or (app and app.superuser):
        return None

    entities = []
    if app:
        entities.append(('application', app, list(app.access_control_groups.all())))
    elif user:
        entities.append(('user', user, list(user.access_control_groups.all())))
    else:
        # This should not be possible as it means not authenticated but better
        # safe than sorry.
        raise PermissionDenied('Missing authentication!')

    # Check all objects touched by this commit
    for obj in chain(
        created_objects.values(),
        changed_objects.values(),
        deleted_objects.values(),
    ):
        # Check app or if not present user permissions
        for entity_class, entity_name, groups in entities:
            acl_violations = {acl: _acl_violations(unchanged_objects, obj, acl) for acl in groups}

            # If all ACLs resulted in violations, none of them allowed the edit
            # Build a verbose error message and abort the commit
            if all(acl_violations.values()):
                msg = 'Insufficient access rights to object "{}" for {} "{}": '.format(
                    obj['hostname'], entity_class, entity_name
                )
                for acl, violations in acl_violations.items():
                    msg += ' '.join(violations)

                logger.debug(msg)
                raise PermissionDenied(msg)


def _acl_violations(touched_objects, pending_changes, acl):
    """Check if ACL allows all the changes to obj

    An ACL can fail to validate in two ways.  Every ACL has a filter describing
    which objects it is applicable to.  If the object doesn't match this filter
    the ACL is violated.  Secondly ACLs include a whitelist of attributes that
    may be changed.  If another attribute is changed, the ACL is violated.

    Just because we return ACL violations here doesn't mean the user isn't
    allowed to make a change.  Another ACL might allow it later on.

    For more context read the _access_control() doc string.

    Returns a list of human-readable ACL violations on failure.
    Returns None on success.
    """

    violations = []

    # Check whether the object matches all the attribute filters of the ACL
    for attribute_id, attribute_filter in acl.get_filters().items():
        # TODO: This relies on the object to have all attributes that are
        #  present in the attribute_filter which currently works because
        #  we fetch all attributes in commit_query (joined_attribtues).
        #  This method would be better of not relying on the caller
        #  making sure passing down all relevant attributes which isn't
        #  even documented.
        if pending_changes['object_id'] in touched_objects:
            # If the object already exists ensure the ACL matches the status
            # quo and not the wanted changes.
            to_compare = touched_objects.get(pending_changes['object_id'])
        else:
            # Otherwise check if the ACL allows the "to be" object.
            to_compare = pending_changes

        if not attribute_filter.matches(to_compare.get(attribute_id)):
            violations.append(
                'Object is not covered by ACL "{}", Attribute "{}" ' 'does not match the filter "{}".'.format(
                    acl,
                    attribute_id,
                    attribute_filter,
                )
            )

    # If this ACL is not applicable to this object, we can bail out right away
    if violations:
        return violations

    # For existing objects we only check attributes which were changed
    # For new objects we only check attributes different to their default
    if pending_changes['object_id'] in touched_objects:
        old_object = touched_objects[pending_changes['object_id']]
    else:
        old_object = get_default_attribute_values(pending_changes['servertype'])

    # Gather attribute ids this ACL allows changing
    attribute_ids = acl.get_permissible_attribute_ids()

    # Check whether all changed attributes are on this ACLs attribute whitelist
    for attribute_id, attribute_value in pending_changes.items():
        if attribute_id not in attribute_ids and attribute_value != old_object[attribute_id]:
            is_related_via: bool = ServertypeAttribute.objects.filter(
                servertype_id=pending_changes['servertype'],
                attribute_id=attribute_id,
                related_via_attribute__isnull=False,
            ).exists()
            if is_related_via:
                # Attributes which are related via another servertype can be
                # skipped because permission to change the value is checked
                # at the target servertype where the actual change takes place.
                continue

            violations.append(
                'Change is not covered by ACL "{}", Attribute "{}" was '
                'modified despite not beeing whitelisted.'.format(
                    acl,
                    attribute_id,
                )
            )

    return violations or None


def _log_changes(user, app, changed, created_objects, deleted_objects):
    changes = list()
    commit = ChangeCommit(user=user, app=app)

    excl_attrs = Attribute.objects.filter(history=False).values_list(flat=True)
    for updates in changed:
        # At least one attribute aside from object_id has changed.
        if len(updates.keys() - excl_attrs) > 1:
            # Get changes for attributes that should be logged.
            to_log = {k: v for k, v in updates.items() if k not in excl_attrs}
            changes.append(
                Change(
                    object_id=updates['object_id'],
                    change_type=Change.Type.CHANGE,
                    change_json=to_log,
                    commit=commit,
                )
            )

    for attributes in deleted_objects.values():
        changes.append(
            Change(
                object_id=attributes['object_id'],
                change_type=Change.Type.DELETE,
                change_json=attributes,
                commit=commit,
            )
        )

    for obj in created_objects.values():
        changes.append(
            Change(
                object_id=obj['object_id'],
                change_type=Change.Type.CREATE,
                change_json=obj,
                commit=commit,
            )
        )

    if changes:
        commit.save()
        Change.objects.bulk_create(changes)


def _fetch_servers(object_ids):
    servers = {s.server_id: s for s in Server.objects.select_for_update().filter(server_id__in=object_ids)}
    for object_id in object_ids:
        if object_id in servers:
            continue
        raise CommitError('Cannot find object with id {}'.format(object_id))

    return servers


def _materialize(servers, joined_attributes):
    return {o['object_id']: o for o in QueryMaterializer(list(servers.values()), joined_attributes)}


def _get_servertype_attributes(servers):
    servertype_attributes = dict()
    for servertype_id in {s['servertype'] for s in servers.values()}:
        servertype_attributes[servertype_id] = dict()
        for sa in Servertype.objects.get(pk=servertype_id).attributes.all():
            servertype_attributes[servertype_id][sa.attribute_id] = sa

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
                attribute_id not in attributes
                or
                # Attributes related via another one, cannot be changed.
                attributes[attribute_id].related_via_attribute
            ):
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


def _validate_regexp(changes, servers, attribute_lookup):
    for attribute_changes in changes:
        object_id = attribute_changes['object_id']
        for attribute_id, change in attribute_changes.items():
            if attribute_id in Attribute.specials:
                continue

            attribute = attribute_lookup[attribute_id]
            if not attribute.regexp:
                continue

            action = change['action']
            if action == 'update' or action == 'new':
                if change['new'] is None:
                    continue
                if not attribute.regexp_match(change['new']):
                    yield object_id, attribute_id
            elif action == 'multi':
                for value in change['add']:
                    if not attribute.regexp_match(value):
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
                    if json_encode_extra(server[attr]) != str(change['old']):
                        newer.append((object_id, attr, server[attr]))
                except KeyError:
                    newer.append((object_id, attr, None))

    return newer


def _build_error_message(violations_attribs, violations_readonly, violations_regexp, violations_required):
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
                message.append('{0}: {1} (#affected: {2})'.format(message_type, vattr, num_affected))

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
        value_multi = isinstance(value, (list, set)) or hasattr(value, '_proxied_set')

        if attribute.multi and not value_multi:
            raise CommitError(
                '{0} is a multi attribute, but {1} of type {2} given.'.format(
                    attribute, repr(value), type(value).__name__
                )
            )
        if not attribute.multi and value_multi:
            raise CommitError(
                '{0} is not a multi attribute, but {1} of type {2} given.'.format(
                    attribute, repr(value), type(value).__name__
                )
            )

        # Ignore nulls
        if not value_multi and value is None:
            continue

        # Ignore the virtual attribute types
        if attribute.type in ['reverse', 'supernet']:
            continue

        yield attribute, value


def _validate_real_attributes(servertype, real_attributes):  # NOQA: C901
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

        if attribute.regexp:
            if attribute.multi:
                for val in value:
                    if not attribute.regexp_match(str(val)):
                        violations_regexp.append(attribute.pk)
            elif not attribute.regexp_match(value):
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

    server = Server(
        hostname=hostname,
        intern_ip=intern_ip,
        servertype=servertype,
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
            regexp_msg = 'Attributes violating regexp: {0}. '.format(', '.join(violations_regexp))
        else:
            regexp_msg = ''
        if violations_required:
            required_msg = 'Attributes violating required: {0}.'.format(', '.join(violations_required))
        else:
            required_msg = ''

        raise CommitError(
            'Validation failed. {0}{1}'.format(regexp_msg, required_msg),
            violations_regexp + violations_required,
        )
    if violations_attribs:
        raise CommitError(
            'Attributes {0} are not defined on ' "this servertype. You can't skip this validation!".format(
                ', '.join(violations_attribs)
            ),
            violations_regexp + violations_required + violations_attribs,
        )
