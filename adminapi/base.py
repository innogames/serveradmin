from distutils.util import strtobool
from itertools import chain


class DatasetError(Exception):
    pass


class QueryError(DatasetError):
    pass


class BaseQuerySet(object):
    def __init__(self, filters):
        self._filters = filters
        self._results = None
        self._restrict = None
        self._order_by = None

    def __iter__(self):
        return iter(self.get_results())

    def __len__(self):
        return len(self.get_results())

    def __bool__(self):
        return bool(self.get_results())

    def __repr__(self):
        # QuerySet is not used directly but through query function
        kwargs = ', '.join(
            '{0}={1!r}'.format(k, v) for k, v in self._filters.items()
        )
        query_repr = 'query({0})'.format(kwargs)

        if self._restrict:
            query_repr += '.restrict({0})'.format(', '.join(self._restrict))

        return query_repr

    def get_lookup(self, attr):
        lookup = {}
        for host in self:
            if attr in host:
                lookup[host[attr]] = host
        return lookup

    def restrict(self, *attrs):
        if not attrs:
            return self

        if isinstance(attrs[0], (list, set, tuple)):
            attrs = attrs[0]

        self._restrict = {str(a) for a in attrs}

        return self

    def get(self):
        results = self.get_results()
        if len(results) != 1:
            raise DatasetError('get() requires exactly 1 matched object')
        return results[0]

    def is_dirty(self):
        return any(s.is_dirty() for s in self)

    def commit(self, skip_validation, force_changes):
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
            if not obj.is_deleted():
                obj.update(attrs)
        return self

    def iterattrs(self, attr='hostname'):
        return (obj[attr] for obj in self)

    def order_by(self, *attribute_ids):
        self._order_by = attribute_ids
        return self

    def get_results(self):
        if self._results is None:
            self._fetch_results()
        return self._results

    def _fetch_results(self):
        raise NotImplementedError()

    def _confirm_changes(self):
        for obj in self:
            obj._confirm_changes()

    def _build_commit_object(self):
        commit = {
            'deleted': [],
            'changes': {},
        }

        for obj in self:
            if obj.is_deleted():
                commit['deleted'].append(obj.object_id)
            elif obj.is_dirty():
                commit['changes'][obj.object_id] = obj._serialize_changes()

        return commit


class BaseServerObject(dict):
    """This class must redefine all mutable methods of the dict class
    to cast multi attributes and to validate the values.
    """

    def __init__(self, attributes=[], object_id=None, queryset=None):
        # Loop through ourself afterwards would be more efficient, but
        # this would give the caller already initialised object in case
        # anything fails.
        attributes = dict(attributes)
        for attribute_id, value in attributes.items():
            if isinstance(value, (tuple, list, set, frozenset)):
                attributes[attribute_id] = MultiAttr(value, self, attribute_id)
        super(BaseServerObject, self).__init__(attributes)
        self.object_id = object_id
        self._deleted = False
        self._queryset = queryset
        self.old_values = {}

    def __hash__(self):
        """Make the objects hashable

        Note that it will not work for objects which doesn't have object_id.
        It is the callers responsibility not to use the them in hashable
        context.  We could try harder to make them hashable with a fallback
        method, but that would lead them to considered as different objects
        after they got an object_id.
        """

        return self.object_id

    def __repr__(self):
        parent_repr = super(BaseServerObject, self).__repr__()
        if not self.object_id:
            return 'ServerObject({0})'.format(parent_repr)
        return 'ServerObject({0}, {1})'.format(parent_repr, self.object_id)

    def is_dirty(self):
        return bool(self.old_values) or self._deleted or self.object_id is None

    def is_deleted(self):
        return self._deleted

    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        self._deleted = False
        for attr, old_value in self.old_values.items():
            super(BaseServerObject, self).__setitem__(attr, old_value)
        self.old_values.clear()

    def delete(self):
        self._deleted = True

    def _serialize_changes(self):
        changes = {}
        for key, old_value in self.old_values.items():
            new_value = self[key]
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
        changes = {}
        if self.is_dirty():
            changes[self.object_id] = self._serialize_changes()
        return {
            'deleted': [self.object_id] if self.is_deleted() else [],
            'changes': changes,
        }

    def _save_old_value(self, key):
        if key not in self.old_values:
            old_value = self[key]
            if isinstance(old_value, MultiAttr):
                self.old_values[key] = old_value.copy()
            else:
                self.old_values[key] = old_value

    def __setitem__(self, key, value):
        if self._deleted:
            raise DatasetError('Cannot set attributes to deleted server')
        self.validate(key, value)
        if isinstance(self[key], MultiAttr):
            # Multi attributes are guaranteed to exist as MultiAttr, so
            # we can always get the previous datatype from the existing
            # value.
            value = MultiAttr(value, self, key, self[key].datatype)
        if key not in self.old_values or self.old_values[key] != value:
            self._save_old_value(key)
        return super(BaseServerObject, self).__setitem__(key, value)

    def validate(self, key, value):
        if key not in self:
            raise KeyError(
                'Cannot set nonexistent attribute "{}"'.format(key)
            )
        if isinstance(self[key], MultiAttr):
            # We are not extensively validating multi attributes.  Their
            # values will validated by the MultiAttr class.
            if not isinstance(value, (tuple, list, set, frozenset)):
                raise TypeError('Attribute "{}" must be multi'.format(key))
        elif isinstance(self[key], bool):
            # Boolean attributes are guaranteed to exist as booleans, so
            # we can rely on the existing value.
            if not isinstance(value, bool):
                raise TypeError('Attribute "{}" must be a boolean'.format(key))
        elif value is not None:
            datatype = type(self[key]) if self[key] is not None else None
            if not datatype and self.old_values.get(key) is not None:
                datatype = type(self.old_values[key])
            _validate_value(key, value, datatype)

    def __delitem__(self, key):
        self[key] = None

    def clear(self):
        for key in self:
            del self[key]

    def pop(self, key, default=None):
        value = self.get(key, default)
        del self[key]
        return value

    def popitem(self):
        for key in self.keys():
            break
        else:
            raise KeyError()
        return self.pop(key)

    def set(self, key, value):
        if isinstance(self[key], MultiAttr):
            self[key].add(value)
        elif type(self[key]) is bool:
            self[key] = strtobool(value)
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


class MultiAttr(set):
    """This class must redefine all mutable methods of the set class
    to maintain the old values on the BaseServerObject.
    """

    def __init__(self, other, server_object, attribute_id, datatype=None):
        super(MultiAttr, self).__init__(other)
        self._server_object = server_object
        self._attribute_id = attribute_id
        self.datatype = self._validate(attribute_id, datatype)

    def _validate(self, attribute_id, datatype):
        """This method accepts class properties as arguments to be called
        with normal sets."""
        for elem in self:
            datatype = _validate_value(attribute_id, elem, datatype)
        return datatype

    def __str__(self):
        return ' '.join(str(x) for x in self)

    def copy(self):
        return MultiAttr(
            self, self._server_object, self._attribute_id, self.datatype
        )

    def add(self, elem):
        if elem in self:
            return
        self.datatype = _validate_value(
            self._attribute_id, elem, self.datatype
        )
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).add(elem)

    def remove(self, elem):
        if elem in self:
            self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).remove(elem)
        if not self:
            self.datatype = None

    def discard(self, elem):
        if elem in self:
            self.remove(elem)

    def pop(self):
        for elem in self:
            break
        else:
            raise KeyError()
        self.remove(elem)
        return elem

    def clear(self):
        if not self:
            return
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).clear()
        self.datatype = None

    def update(self, *others):
        if not others:
            return
        new = others[0]
        for other in others[1:]:
            new |= other
        if not new - self:
            return
        MultiAttr._validate(new, self._attribute_id, self.datatype)
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).difference_update(new)

    def intersection_update(self, *others):
        if not others:
            return
        new = others[0]
        for other in others[1:]:
            new &= other
        if not self - new:
            return
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).intersection_update(new)

    def difference_update(self, *others):
        if not others:
            return
        new = others[0]
        for other in others[1:]:
            new |= other
        if not self & new:
            return
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).difference_update(new)

    def symmetric_difference_update(self, other):
        if not other:
            return
        new = other - self
        if new:
            MultiAttr._validate(new, self._attribute_id, self.datatype)
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).symmetric_difference_update(other)


def _validate_value(attribute_id, value, datatype=None):
    """It accepts an optional datatype to validate the values.  The values
    are not necessarily be an instance of this datatype.  They will be checked
    a common super-class.  The function returns the found super-class,
    so that callers can save and reuse it.  When the datatype is not
    provided, then it will return the class of the value.

    The reason behind this method is to preserve the datatype as much as
    possible without being too strict.  Just getting the top level class
    on the inheritance tree after "object" would increase the errors, because
    with multi-inheritance there can be different top level classes.
    Therefore, this method is not really deterministic.  It can cause
    unexpected behavior, but it is the best we can do.
    """

    # Special types that are allowed only in some contexts.
    special_datatypes = (
        type,
        bool,
        tuple,
        list,
        set,
        frozenset,
        dict,
        BaseException,
        type(None),
    )
    assert datatype not in special_datatypes
    if isinstance(value, special_datatypes):
        raise TypeError(
            'Attribute "{}" value cannot be from {}'
            .format(attribute_id, type(value))
        )

    assert datatype != object
    if type(value) == object:
        raise TypeError(
            'Attribute "{}" value cannot be a generic object'
            .format(attribute_id)
        )

    newtype = type(value)
    if datatype is None or issubclass(datatype, newtype):
        return newtype

    for supertype in datatype.mro():
        if issubclass(newtype, supertype) and supertype != object:
            return supertype

    raise TypeError(
        'Attribute "{}" value from {} is not compatible with '
        'existing value from {}'
        .format(attribute_id, type(value), datatype)
    )
