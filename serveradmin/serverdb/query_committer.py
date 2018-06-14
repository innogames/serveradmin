import json
from ipaddress import ip_network, ip_interface
from itertools import chain

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.dispatch.dispatcher import Signal

from adminapi.dataset import DatasetCommit
from adminapi.request import json_encode_extra
from serveradmin.hooks.slots import HookSlot
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
    Project,
)
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)

pre_commit = Signal()


class QueryCommitter:
    def __init__(
        self,
        created=[],
        changed=[],
        deleted=[],
        app=None,
        user=None,
    ):
        self.created = created
        self.changed = changed
        self.deleted = deleted
        self.app = app
        self.user = user or app.owner

    def __call__(self):
        pre_commit.send_robust(
            QueryCommitter,
            created=self.created,
            changed=self.changed,
            deleted=self.deleted,
        )

        # If non-empty, the commit will go through the backend, but an error
        # will be shown on the client.
        self.warnings = []

        with transaction.atomic():
            self._fetch()
            self._validate()
            created_objects, changed_objects = self._apply()
            self._access_control(created_objects, changed_objects)
            self._log_changes(created_objects)

        if self.warnings:
            warnings = '\n'.join(self.warnings)
            raise CommitIncomplete(
                'Commit was written, but hooks failed:\n\n{}'.format(warnings)
            )

        return DatasetCommit(
            list(created_objects.values()),
            list(changed_objects.values()),
            list(self._deleted_objects.values()),
        )

    def _fetch(self):
        self._changed_servers = _fetch_servers(
            set(c['object_id'] for c in self.changed)
        )
        self._changed_objects = _materialize_servers(self._changed_servers)

        self._deleted_servers = _fetch_servers(self.deleted)
        self._deleted_objects = _materialize_servers(self._deleted_servers)

    def _validate(self):
        servertype_attributes = _get_servertype_attributes(
            self._changed_objects
        )

        # Attributes must be always validated
        violations_attribs = _validate_attributes(
            self.changed, self._changed_objects, servertype_attributes
        )
        violations_readonly = _validate_readonly(
            self.changed, self._changed_objects
        )
        violations_regexp = list(_validate_regexp(
            self.changed,
            self._changed_objects,
            servertype_attributes,
        ))
        violations_required = _validate_required(
            self.changed,
            self._changed_objects,
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

        newer = _validate_commit(self.changed, self._changed_objects)
        if newer:
            raise CommitNewerData('Newer data available', newer)

    def _log_changes(self, created_objects):
        commit = ChangeCommit.objects.create(app=self.app, user=self.user)

        for updates in self.changed:
            ChangeUpdate.objects.create(
                commit=commit,
                server_id=updates['object_id'],
                updates_json=json.dumps(updates, default=json_encode_extra),
            )

        for attributes in self._deleted_objects.values():
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

    def _apply(self):
        # Changes should be applied in order to prevent integrity errors.
        self._delete_attributes()
        self._delete_servers()
        created_objects = self._create_servers()
        self._update_servers()
        self._upsert_attributes()

        # Re-fetch servers before invoking hook, otherwise the hook will
        # receive incomplete data.
        changed_objects = _materialize_servers(self._changed_servers)
        try:
            on_server_attribute_changed.invoke(
                commit=self,
                servers=list(changed_objects.values()),
                changed=self.changed,
            )
        except CommitIncomplete as error:
            self.warnings.append(
                'Commit hook failed:\n{}'.format(' '.join(error.messages))
            )

        return created_objects, changed_objects

    def _delete_attributes(self):
        # We first have to delete all of the relation attributes
        # to avoid integrity errors.  Other attributes will just go away
        # with the servers.
        if self.deleted:
            (
                ServerRelationAttribute.objects
                .filter(server_id__in=self.deleted)
                .delete()
            )

        for changes in self.changed:
            object_id = changes['object_id']

            for attribute_id, change in changes.items():
                if attribute_id == 'object_id':
                    continue

                server = self._changed_servers[object_id]
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
            for server in self._deleted_servers.values():
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

    def _create_servers(self):
        self._created_servers = {}
        for attributes in self.created:
            if 'hostname' not in attributes:
                raise CommitError('"hostname" attribute is required.')
            hostname = attributes['hostname']

            servertype = _get_servertype(attributes)
            project = _get_project(attributes)
            intern_ip = _get_ip_addr(servertype, attributes)

            real_attributes = dict(_get_real_attributes(attributes))
            _validate_real_attributes(servertype, real_attributes)

            server = _insert_server(
                hostname,
                intern_ip,
                servertype,
                project,
                real_attributes,
            )

            created_server = {k.pk: v for k, v in real_attributes.items()}
            created_server['hostname'] = hostname
            created_server['servertype'] = servertype.pk
            created_server['project'] = project.pk
            created_server['intern_ip'] = intern_ip

            self._created_servers[server.server_id] = server

        return _materialize_servers(self._created_servers)

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
                server = self._changed_servers[object_id]
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

                server = self._changed_servers[object_id]

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

    def _access_control(self, created_objects, changed_objects):
        entities = list()
        if not self.user.is_superuser:
            entities.append((
                'user',
                self.user,
                list(self.user.access_control_groups.all()),
            ))
        if self.app and not self.app.superuser:
            entities.append((
                'application',
                self.app,
                list(self.app.access_control_groups.all()),
            ))

        for server in chain(
            created_objects.values(),
            changed_objects.values(),
            self._deleted_objects.values(),
        ):
            for entity_class, entity_name, groups in entities:
                if not any(self._can_access_server(server, g) for g in groups):
                    raise PermissionDenied(
                        'Insufficient access rights to server "{}" for {} "{}"'
                        .format(server['hostname'], entity_class, entity_name)
                    )

    def _can_access_server(self, new_object, acl):
        if not all(
            f.matches(new_object.get(a))
            for a, f in acl.get_filters().items()
        ):
            return False

        if new_object['object_id'] in self._changed_objects:
            old_object = self._changed_objects[new_object['object_id']]
        else:
            old_object = get_default_attribute_values(new_object['servertype'])

        attribute_ids = {a.pk for a in acl.attributes.all()}
        if not all(
            a in attribute_ids or v == old_object[a] or
            Attribute.objects.get(pk=a).readonly
            for a, v in new_object.items()
        ):
            return False

        return True


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
            changes = {c['object_id']: c for c in changed}
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
    'commit_server_changed', servers=list, changed=list, commit=QueryCommitter
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


def _materialize_servers(servers):
    return {
        o['object_id']: o
        for o in QueryMaterializer(list(servers.values()), None)
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


def _get_servertype(attributes):
    if 'servertype' not in attributes:
        raise CommitError('"servertype" attribute is required.')
    try:
        return Servertype.objects.get(pk=attributes['servertype'])
    except Servertype.DoesNotExist:
        raise CommitError('Unknown servertype: ' + attributes['servertype'])


def _get_project(attributes):
    if 'project' not in attributes:
        raise CommitError('"project" attribute is required.')

    return Project.objects.select_for_update().get(pk=attributes['project'])


def _get_ip_addr(servertype, attributes):
    networks = tuple(_get_networks(attributes))
    if servertype.ip_addr_type == 'null':
        return _get_null_ip_addr(attributes, networks)
    if servertype.ip_addr_type in ('host', 'loadbalancer'):
        return _get_host_ip_addr(attributes, networks)
    return _get_network_ip_addr(attributes, networks)


def _get_networks(attributes):
    for attribute in Attribute.objects.all():
        if attribute.type == 'supernet' and attributes.get(attribute.pk):
            attribute_value = attributes[attribute.pk]
            try:
                server = Server.objects.get(hostname=attribute_value)
            except Server.DoesNotExist:
                raise CommitError(
                    'No server named "{0}" for attribute "{1}"'
                    .format(attribute_value, attribute)
                )
            target_servertype = attribute.target_servertype
            if server.servertype != target_servertype:
                raise CommitError(
                    'Matching server "{0}" for attribute "{1}" is not from '
                    'servertype "{2}"'
                    .format(attribute_value, attribute, target_servertype)
                )
            yield server.intern_ip.network


def _get_null_ip_addr(attributes, networks):
    if attributes.get('intern_ip') is not None:
        raise CommitError('"intern_ip" has to be None.')
    if networks:
        raise CommitError('There must not be any networks.')

    return None


def _get_host_ip_addr(attributes, networks):
    if 'intern_ip' not in attributes:
        if not networks:
            raise CommitError(
                '"intern_ip" is not given, and no networks could be found.'
            )
        intern_ip = _choose_ip_addr(networks)
        if intern_ip is None:
            raise CommitError(
                'No IP address could be selected from the given networks.'
            )
        return intern_ip

    try:
        intern_ip = ip_interface(attributes['intern_ip'])
    except ValueError as error:
        raise CommitError(str(error))

    _check_in_networks(networks, intern_ip.network)
    return intern_ip.ip


def _get_network_ip_addr(attributes, networks):
    if 'intern_ip' not in attributes:
        raise CommitError('"intern_ip" attribute is required.')

    try:
        intern_ip = ip_network(attributes['intern_ip'])
    except ValueError as error:
        raise CommitError(str(error))

    _check_in_networks(networks, intern_ip)
    return intern_ip


# XXX: Deprecated
def _choose_ip_addr(networks):
    smallest_network = None
    for network in networks:
        if smallest_network is not None:
            if not network.overlaps(smallest_network):
                raise CommitError('Networks are not overlapping.')
            if network.prefixlen < smallest_network.prefixlen:
                continue
        smallest_network = network
    if smallest_network is not None:
        return _get_free_ip_addr(smallest_network)


# XXX: Deprecated
def _get_free_ip_addr(network):
    used = {i.ip for i in (
        Server.objects
        .filter(intern_ip__net_contained_or_equal=network)
        .order_by()     # Clear ordering for database performance
        .values_list('intern_ip', flat=True)
    )}
    for ip_addr in ip_network(network).hosts():
        if ip_addr not in used:
            return ip_addr
    return None


def _check_in_networks(networks, intern_ip_network):
    for network in networks:
        if (
            network.prefixlen > intern_ip_network.prefixlen or
            not network.overlaps(intern_ip_network)
        ):
            raise CommitError(
                '"intern_ip" does not belong to the given networks.'
            )


def _get_real_attributes(attributes):
    for attribute_id, value in attributes.items():
        attribute = Attribute.objects.get(pk=attribute_id)
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

        # Ignore special attributes
        if attribute.special:
            continue

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


def _insert_server(
    hostname,
    intern_ip,
    servertype,
    project,
    attributes,
):

    if Server.objects.filter(hostname=hostname).exists():
        raise CommitError('Server with that hostname already exists')

    server = Server.objects.create(
        hostname=hostname,
        intern_ip=intern_ip,
        _servertype=servertype,
        _project=project,
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
