from itertools import chain


class DatasetError(Exception):
    pass


class BaseQuerySet(object):
    def __init__(self, filters):
        self._filters = filters
        self._results = None
        self._restrict = None
        self._augmentations = None
        self._order = None

    def __iter__(self):
        self.get_results()
        if self._order is not None:
            order_keys = self._order

            def key_fn(server):
                return tuple(server.get(key) for key in order_keys)
            return iter(sorted(self._results.values(), key=key_fn))

        return iter(self._results.values())

    def __len__(self):
        self.get_results()
        return len(self._results)

    def __bool__(self):
        self.get_results()
        return bool(self._results)

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

    def fetch_now(self):
        self.get_results()
        return self

    def augment(self, *augmentations):
        self._augmentations = set(augmentations)
        return self

    def restrict(self, *attrs):
        if not attrs:
            return self

        if isinstance(attrs[0], (list, set, tuple)):
            attrs = attrs[0]

        self._restrict = {str(a) for a in attrs}

        return self

    def count(self):
        raise NotImplementedError()

    def get(self):
        self.get_results()
        if len(self._results) != 1:
            raise DatasetError('get() requires exactly 1 matched object')
        for value in self._results.values():
            return value

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

    def order_by(self, *attrs):
        self._order = attrs
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
    to cast multi attributes.
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
        if isinstance(value, (tuple, list, set, frozenset)):
            value = MultiAttr(value, self, key)
        if key not in self.old_values or self.old_values[key] != value:
            self._save_old_value(key)
        return super(BaseServerObject, self).__setitem__(key, value)

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

    def __init__(self, other, server_object, attribute_id):
        super(MultiAttr, self).__init__(other)
        self._server_object = server_object
        self._attribute_id = attribute_id

    def __str__(self):
        return ' '.join(str(x) for x in self)

    def __unicode__(self):
        return u' '.join(unicode(x) for x in self)

    def add(self, elem):
        if elem in self:
            return
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).add(elem)

    def remove(self, elem):
        if elem in self:
            self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).remove(elem)

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

    def update(self, *others):
        if not others:
            return
        new = others[0]
        for other in others[1:]:
            new |= other
        if not new - self:
            return
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
        self._server_object._save_old_value(self._attribute_id)
        super(MultiAttr, self).symmetric_difference_update(other)
