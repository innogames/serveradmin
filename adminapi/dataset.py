"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

from distutils.util import strtobool
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from itertools import chain
from types import GeneratorType

from adminapi import api
from adminapi.datatype import validate_value, json_to_datatype
from adminapi.filters import Any, BaseFilter, ContainedOnlyBy
from adminapi.request import send_request, json_encode_extra
from adminapi.exceptions import DatasetError, AdminapiException

NEW_OBJECT_ENDPOINT = '/dataset/new_object'
COMMIT_ENDPOINT = '/dataset/commit'
QUERY_ENDPOINT = '/dataset/query'


class BaseQuery(object):
    def __init__(self, filters=None, restrict=['hostname'], order_by=None):
        if filters is None:
            self._filters = None
            self._restrict = None
            self._order_by = None
            self._results = []
            return

        self._filters = {
            a: f if isinstance(f, BaseFilter) else BaseFilter(f)
            for a, f in filters.items()
        }

        self._restrict = restrict
        self._order_by = order_by
        self._results = None

    def __iter__(self):
        return iter(self._get_results())

    def __len__(self):
        return len(self._get_results())

    def __bool__(self):
        return bool(self._get_results())

    def __repr__(self):
        args = []
        if self._filters is not None:
            args.append(repr(self._filters))
        if self._restrict is not None:
            args.append('restrict=' + repr(self._restrict))
        if self._order_by is not None:
            args.append('order_by=' + repr(self._order_by))
        return 'Query({})'.format(', '.join(args))

    @property
    def _restrict(self):
        return self.__restrict

    @_restrict.setter
    def _restrict(self, new_restrict):
        def _ensure_object_id(restrict):
            # The Query classes expect to always get an object_id to correlate
            # objects when commiting them. If the user didn't ask for it, we
            # will add it here.
            if restrict is None:
                return None

            # Deprecated, needed for .restrict()
            if isinstance(restrict, set):
                restrict = list(restrict)

            if not isinstance(restrict, list):
                raise TypeError('Restrict must be a list')

            if 'object_id' not in restrict:
                # Don't change the original restrict to avoid the user working
                # with unexpected elements.
                restrict = restrict.copy()
                restrict.append('object_id')

            return [
                i if not isinstance(i, dict) else
                {k: _ensure_object_id(v) for k, v in i.items()}
                for i in restrict
            ]

        self.__restrict = _ensure_object_id(new_restrict)

    def _get_results(self):
        if self._results is None:
            self._results = self._fetch_results()
        return self._results

    def _fetch_results(self):
        raise NotImplementedError()

    def _fetch_new_object(self, servertype):
        raise NotImplementedError()

    def new_object(self, servertype):
        obj = self._fetch_new_object(servertype)
        if self._filters:
            for attribute, filt in self._filters:
                if attribute not in obj:
                    raise DatasetError(
                        '"{}" is not on the new object'.format(attribute)
                    )
                if not filt.matches(obj[attribute]):
                    raise DatasetError(
                        '"{}" is not consistent with the query'
                        .format(attribute)
                    )

        self._get_results().append(obj)

        return obj

    def get_lookup(self, attr):
        lookup = {}
        for host in self:
            if attr in host:
                lookup[host[attr]] = host
        return lookup

    # XXX: Deprecated
    def restrict(self, *attrs):
        if not attrs:
            return self

        if isinstance(attrs[0], (list, set, tuple)):
            attrs = attrs[0]

        self._restrict = {str(a) for a in attrs}

        return self

    # XXX: Deprecated
    def order_by(self, *attribute_ids):
        self._order_by = attribute_ids
        return self

    def get(self):
        results = self._get_results()
        if len(results) != 1:
            raise DatasetError(
                'get() requires exactly 1 matched object, {} found'.format(
                    len(results)
                ))
        return results[0]

    # XXX: Deprecated
    def is_dirty(self):
        return any(s.is_dirty() for s in self)

    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        for obj in self:
            obj.rollback()
        return self

    def delete(self):
        for obj in self:
            obj.delete()
        return self

    def update(self, **attrs):
        for obj in self:
            obj.update(attrs)
        return self

    def iterattrs(self, attr='hostname'):
        return (obj[attr] for obj in self)

    def _confirm_changes(self):
        for obj in self:
            obj._confirm_changes()

    def _build_commit_object(self):
        commit = {
            'created': [],
            'changed': [],
            'deleted': [],
        }

        for obj in self:
            state = obj.commit_state()

            if state == 'created':
                commit['created'].append(obj)
            elif state == 'changed':
                commit['changed'].append(obj._serialize_changes())
            elif state == 'deleted':
                commit['deleted'].append(obj.object_id)

        return commit

    def get_network_ip_addrs(self):
        if self._restrict is not None and 'intern_ip' not in self._restrict:
            raise DatasetError('"intern_ip" is not queried')

        for obj in self:
            addr = obj['intern_ip']
            if isinstance(addr, (IPv4Network, IPv6Network)):
                yield addr

    def get_free_ip_addrs(self):
        networks = list(self.get_network_ip_addrs())
        if not networks:
            raise DatasetError('No networks')

        # Index host and network addresses separately
        used_hosts = set()
        used_networks = list()
        for obj in type(self)({
            'intern_ip': Any(*(ContainedOnlyBy(n) for n in networks)),
        }, ['intern_ip']):
            addr = obj['intern_ip']
            if isinstance(addr, (IPv4Address, IPv6Address)):
                used_hosts.add(addr)
            else:
                assert isinstance(addr, (IPv4Network, IPv6Network))
                used_networks.append(addr)

        # Now, we are ready to return.
        for network in networks:
            for host in network.hosts():
                for other_network in used_networks:
                    if host in other_network:
                        break
                else:
                    if host not in used_hosts:
                        yield host

    def get_free_ip_addr(self, lock=True):
        """Get one free IP address from network

        This will give you exactly one free IP address for the queried network
        and lock it to avoid somebody else using it. If you do not care you
        can set lock to false but may need to handle the CommitError with the
        duplicate IP on your own.

        :param lock: Lock free IP address for 60 seconds

        :return:
        """

        if not lock:
            try:
                return next(self.get_network_ip_addrs())
            except StopIteration:
                raise AdminapiException('No free IPs left!')

        lock_api = api.get('api')
        for free_ip in self.get_free_ip_addrs():
            if lock_api.lock(free_ip) is True:
                return free_ip

        raise AdminapiException('No free IPs left!')


class Query(BaseQuery):
    def _fetch_new_object(self, servertype):
        response = send_request(
            NEW_OBJECT_ENDPOINT, [('servertype', servertype)]
        )
        return _format_obj(response['result'])

    def commit(self):
        commit = self._build_commit_object()
        result = send_request(COMMIT_ENDPOINT, post_params=commit)

        if result['status'] == 'error':
            _handle_exception(result)

        self.num_dirty = 0
        for obj in self:
            obj._confirm_changes()

    def _fetch_results(self):
        request_data = {'filters': self._filters}
        if self._restrict is not None:
            request_data['restrict'] = self._restrict
        if self._order_by is not None:
            request_data['order_by'] = self._order_by

        response = send_request(QUERY_ENDPOINT, post_params=request_data)
        if response['status'] == 'error':
            _handle_exception(response)
        return [_format_obj(s) for s in response['result']]


class DatasetObject(dict):
    """This class must redefine all mutable methods of the dict class
    to cast multi attributes and to validate the values.
    """

    def __init__(self, attributes=[], object_id=None):
        # Loop through ourself afterwards would be more efficient, but
        # this would give the caller already initialised object in case
        # anything fails.
        attributes = dict(attributes)
        for attribute_id, value in attributes.items():
            if isinstance(value, (tuple, list, set, frozenset)):
                attributes[attribute_id] = MultiAttr(value, self, attribute_id)
        super(DatasetObject, self).__init__(attributes)
        self.object_id = object_id
        self._deleted = False
        self.old_values = {}

    def __hash__(self):
        """Make the objects hashable

        Note that it will not work for objects which don't have object_id.
        It is the callers responsibility not to use the them in hashable
        context.  We could try harder to make them hashable with a fallback
        method, but that would lead them to considered as different objects
        after they got an object_id.
        """

        return self.object_id

    def __repr__(self):
        parent_repr = super(DatasetObject, self).__repr__()
        if not self.object_id:
            return 'DatasetObject({0})'.format(parent_repr)
        return 'DatasetObject({0}, {1})'.format(parent_repr, self.object_id)

    def commit_state(self):
        if self.object_id is None:
            return 'created'
        if self._deleted:
            return 'deleted'
        for attribute_id, old_value in self.old_values.items():
            if (
                json_encode_extra(self[attribute_id]) !=
                json_encode_extra(old_value)
            ):
                return 'changed'
        return 'consistent'

    # XXX: Deprecated
    def is_dirty(self):
        return self.commit_state() != 'consistent'

    # XXX: Deprecated
    def is_deleted(self):
        return self.commit_state() == 'deleted'

    # XXX: Deprecated
    def rollback(self):
        self._deleted = False
        for attr, old_value in self.old_values.items():
            super(DatasetObject, self).__setitem__(attr, old_value)
        self.old_values.clear()

    def delete(self):
        self._deleted = True

    def _serialize_changes(self):
        changes = {'object_id': self.object_id}
        for key, old_value in self.old_values.items():
            new_value = self[key]

            if (
                json_encode_extra(old_value) ==
                json_encode_extra(new_value)
            ):
                continue

            if isinstance(old_value, MultiAttr):
                action = 'multi'
            else:
                action = 'update'

            change = {'action': action}
            if action == 'update':
                change['old'] = old_value
                change['new'] = new_value
            elif action == 'multi':
                change['remove'] = old_value.difference(new_value)
                change['add'] = new_value.difference(old_value)

            changes[key] = change

        return changes

    def _confirm_changes(self):
        self.old_values.clear()
        if self._deleted:
            self.object_id = None
            self._deleted = False

    def _build_commit_object(self):
        state = self.commit_state()

        commit_obj = {
            'created': [],
            'changed': [],
            'deleted': [],
        }
        if state == 'created':
            commit_obj['created'].append(self)
        elif state == 'changed':
            commit_obj['changed'].append(self._serialize_changes())
        elif state == 'deleted':
            commit_obj['deleted'].append(self.object_id)

        return commit_obj

    def _save_old_value(self, key):
        # We need to save the first version only.
        if key not in self.old_values:
            old_value = self[key]
            if isinstance(old_value, MultiAttr):
                self.old_values[key] = old_value.copy()
            else:
                self.old_values[key] = old_value

    def __setitem__(self, key, value):
        if isinstance(self[key], MultiAttr):
            value = MultiAttr(value, self, key)
        elif isinstance(value, GeneratorType):
            value = next(value)

        if self._deleted:
            raise DatasetError('Cannot set attributes to deleted object')
        if key not in self:
            raise DatasetError(
                'Cannot set nonexistent attribute "{}"'.format(key)
            )

        self._save_old_value(key)
        self.validate(key, value)

        return super(DatasetObject, self).__setitem__(key, value)

    def validate(self, key, value):
        # Boolean attributes are guaranteed to exist as booleans, multi
        # attributes are guaranteed to exist as sets, so we can rely on
        # the existing value.
        old_value = self.old_values.get(key, self[key])
        datatype = None
        if isinstance(old_value, bool):
            if not isinstance(value, bool):
                raise TypeError('Attribute "{}" must be a boolean'.format(key))
        elif isinstance(old_value, MultiAttr):
            for elem in old_value | set(value):
                datatype = validate_value(elem, datatype)
        elif value is not None:
            if old_value is not None:
                datatype = type(old_value)
            validate_value(value, datatype)

    def set(self, key, value):
        if isinstance(self[key], MultiAttr):
            self[key].add(value)
        elif type(self[key]) is bool:
            self[key] = bool(strtobool(value))
        elif type(self[key]) is int:
            self[key] = int(value)
        else:
            self[key] = value

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        self[key] = default
        return default

    def update(self, other, **kwargs):
        if hasattr(other, 'items'):
            other = other.items()
        for key, value in chain(other, kwargs.items()):
            self[key] = value

    # XXX: Deprecated
    def commit(self):
        commit = self._build_commit_object()
        result = send_request(COMMIT_ENDPOINT, post_params=commit)

        if result['status'] == 'error':
            _handle_exception(result)

        self._confirm_changes()


class MultiAttr(set):
    """This class must redefine all mutable methods of the set class
    to maintain the old values on the DatasetObject.
    """

    def __init__(self, other, obj, attribute_id):
        super(MultiAttr, self).__init__(other)
        self._obj = obj
        self._attribute_id = attribute_id

    def __str__(self):
        return ' '.join(str(x) for x in self)

    def copy(self):
        return MultiAttr(self, self._obj, self._attribute_id)

    def add(self, elem):
        self._obj[self._attribute_id] = self | {elem}

    def discard(self, elem):
        self._obj[self._attribute_id] = self - {elem}

    def remove(self, elem):
        if elem not in self:
            raise KeyError()
        self.discard(elem)

    def pop(self):
        for elem in self:
            break
        else:
            raise KeyError()
        self.discard(elem)
        return elem

    def clear(self):
        self._obj[self._attribute_id] = set()

    def update(self, *others):
        new = set(self)
        for other in others:
            new |= other
        self._obj[self._attribute_id] = new

    def intersection_update(self, *others):
        new = set(self)
        for other in others:
            new &= other
        self._obj[self._attribute_id] = new

    def difference_update(self, *others):
        new = set(self)
        for other in others:
            new -= other
        self._obj[self._attribute_id] = new

    def symmetric_difference_update(self, other):
        self._obj[self._attribute_id] = self ^ other


class DatasetCommit(object):
    def __init__(self, created, changed, deleted):
        self.created = created
        self.changed = changed
        self.deleted = deleted


# XXX: Deprecated
def _handle_exception(result):
    if result['type'] == 'ValueError':
        exception_class = ValueError
    else:
        exception_class = DatasetError

    #
    # Dear traceback reader,
    #
    # This is not the location of the exception, please read the
    # exception message and figure out what's wrong with your
    # code.
    #
    raise exception_class(result['message'])


def _format_obj(result):
    obj = DatasetObject(object_id=result['object_id'])
    for attribute_id, value in list(result.items()):
        if isinstance(value, list):
            casted_value = MultiAttr(
                (_format_attribute_value(v) for v in value),
                obj,
                attribute_id,
            )
        else:
            casted_value = _format_attribute_value(value)

        dict.__setitem__(obj, attribute_id, casted_value)

    return obj


def _format_attribute_value(value):
    if isinstance(value, dict):
        return _format_obj(value)
    return json_to_datatype(value)
