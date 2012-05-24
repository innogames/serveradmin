from __future__ import print_function
import sys

from adminapi.utils import IP, print_table, print_heading

NonExistingAttribute = object()

class DatasetError(Exception):
    pass

class CommitError(Exception):
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

class BaseQuerySet(object):
    def __init__(self, filters):
        self._filters = filters
        self._results = None
        self._restrict = None
        self._augmentations = None
        self._num_dirty = 0

    def __iter__(self):
        self._get_results()
        return self._results.itervalues()

    def __len__(self):
        self._get_results()
        return len(self._results)

    def augment(self, *augmentations):
        self._augmentations = set(augmentations)
        return self

    def restrict(self, *attrs):
        self._restrict = set(attrs)
        return self

    def count(self):
        raise NotImplementedError()

    def get(self):
        self._get_results()
        if len(self._results) != 1:
            raise DatasetError('get() requires exactly 1 matched object')
        return self._results.itervalues().next()
    
    def is_dirty(self):
        return bool(self._num_dirty)

    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        for obj in self:
            obj.rollback()

    def delete(self):
        for obj in self:
            obj.delete()

    def update(self, **attrs):
        for obj in self:
            if not obj.is_deleted():
                obj.update(attrs)
        return self

    def iterattrs(self, attr='hostname'):
        return (obj[attr] for obj in self)

    def print_list(self, attr='hostname', file=sys.stdout):
        for obj in self:
            print('* {0}'.format(obj[attr]), file=file)

    def print_table(self, *attrs, **kwargs):
        file = kwargs.get('file', sys.stdout)
        table = [attrs]
        for obj in self:
            row = [obj.get(attr, NonExistingAttribute) for attr in attrs]
            table.append(row)
        print_table(table, file=file)

    def print_changes(self, title=lambda x: x['hostname'], file=sys.stdout):
        num_dirty = 0
        for obj in self:
            if obj.is_dirty():
                num_dirty += 1
                obj.print_changes(title, file=file)
                file.write('\n')
        file.write('\n{0} changed and {1} unchanged.\n'.format(num_dirty,
                len(self) - num_dirty))

    def _get_results(self):
        if self._results is None:
            self._results = self._fetch_results()

    def _fetch_results(self):
        raise NotImplementedError()

    def _confirm_changes(self):
        for obj in self:
            obj._confirm_changes()


class BaseServerObject(dict):
    def __init__(self, attributes=None, object_id=None, queryset=None):
        self.object_id = object_id
        self._deleted = False
        self._queryset = queryset
        self.old_values = {}
        if attributes:
            dict.update(self, attributes)

    def __repr__(self):
        if self.object_id:
            return 'ServerObject({0}, {1})'.format(dict.__repr__(self),
                    self.object_id)
        else:
            return 'ServerObject({0})'.format(dict.__repr__(self))

    def is_dirty(self):
        return bool(self.old_values) or self._deleted or self.object_id is None

    def is_deleted(self):
        return self._deleted
    
    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        if self._queryset and self.is_dirty():
            self._queryset._num_dirty -= 1
        self._deleted = False
        for attr, old_value in self.old_values.iteritems():
            dict.__setitem__(self, attr, old_value)
        self.old_values.clear()

    def delete(self):
        if self._queryset and not self.is_dirty():
            self._queryset._num_dirty += 1
        self._deleted = True

    def print_table(self, *attrs, **kwargs):
        file = kwargs.get('file', sys.stdout)
        table = [['Attribute', 'Value']]

        if not attrs:
            for attr, value in self.iteritems():
                table.append((attr, value))
        else:
            for attr in attrs:
                table.append((attr, _format_value(self.get(attr))))
        print_table(table, file=file)

    def print_changes(self, title=None, file=sys.stdout):
        if title:
            if hasattr(title, '__call__'):
                print_title = title(self)
            else:
                print_title = title
            print_heading(print_title, file=file)

        if not self.old_values:
            print('No changes.', file=file)
            return

        table = [('Attribute', 'Old value', 'New value')]
        for attr, old_value in self.old_values.iteritems():
            old_value_fmt = _format_value(old_value)
            table.append((attr, old_value_fmt, self[attr]))

        print_table(table, file=file)

    def _serialize_changes(self):
        changes = {}
        for key, old_value in self.old_values.iteritems():
            new_value = self.get(key, NonExistingAttribute)
            if new_value == NonExistingAttribute:
                action = 'delete'
            elif old_value == NonExistingAttribute:
                action = 'new'
            elif self.queryset.attributes[key]['multi']:
                action = 'multi'
            else:
                action = 'update'

            change = {'action': action}
            if action == 'update':
                change['old'] = old_value
                change['new'] = new_value
            elif action == 'new':
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

    def _save_old_value(self, attr):
        was_dirty_before = self.is_dirty()
        if attr not in self.old_values:
            old_value = self.get(attr, NonExistingAttribute)
            if isinstance(old_value, set):
                self.old_values[attr] = old_value.copy()
            else:
                self.old_values[attr] = old_value
        if self._queryset and not was_dirty_before:
            self._queryset._num_dirty += 1

    def __setitem__(self, k, v):
        if self._deleted:
            raise DatasetError('Can not set attributes on deleted servers')
        if k not in self._queryset.attributes:
            raise DatasetError('No such attribute')
        if self._queryset.attributes[k]['type'] == 'ip':
            v = IP(v)
        if self._queryset.attributes[k]['multi']:
            if not isinstance(v, set):
                raise DatasetError('Multi attributes must be sets')
            v = MultiAttr(v, self, k)
        self._save_old_value(k)
        return dict.__setitem__(self, k, v)
    __setitem__.__doc__ = dict.__setitem__.__doc__

    def __delitem__(self, k):
        self._save_old_value(k)
        return dict.__delitem__(self, k)
    __delitem__.__doc__ = dict.__delitem__.__doc__

    def clear(self):
        for attr in self:
            self._save_old_value(attr)
        return dict.clear(self)
    clear.__doc__ = dict.clear.__doc__
    
    def pop(self, k, d=None):
        if k in self:
            self._save_old_value(k)
        return dict.pop(self, k, d)
    pop.__doc__ = dict.pop.__doc__

    def popitem(self):
        k, v = dict.popitem(self)
        if k not in self.old_values:
            if self._queryset and self.is_dirty():
                self._queryset._num_dirty += 1
            self.old_values[k] = v
        return k, v
    popitem.__doc__ = dict.popitem.__doc__

    def setdefault(self, k, d=None):
        if k not in self:
            self._save_old_value(k)
        return dict.setdefault(k, d)
    setdefault.__doc__ = dict.setdefault.__doc__

    def update(self, E, **F):
        if hasattr(E, 'keys'):
            for k in E:
                self[k] = E[k]
        else:
            for (k, v) in E:
                self[k] = v
        for k in F:
            self[k] = F[k]
    update.__doc__ = dict.update.__doc__

class MultiAttr(set):
    def __init__(self, iterable, server_obj, attr_name):
        if iterable is not None:
            set.__init__(self, iterable)
        self._server_obj = server_obj
        self._attr_name = attr_name

    def add(self, elem):
        self._tell_change()
        set.add(self, elem)
    add.__doc__ = set.add.__doc__

    def clear(self):
        self._tell_change()
        set.clear(self)
    clear.__doc__ = set.clear.__doc__
    
    def difference_update(self, other_set):
        self._tell_change()
        set.difference_update(self, other_set)
    difference_update.__doc__ = set.difference_update.__doc__
    __isub__ = difference_update

    def discard(self, elem):
        self._tell_change()
        set.discard(self, elem)
    discard.__doc__ = set.discard.__doc__

    def intersection_update(self, other_set):
        self._tell_change()
        set.intersection_update(self, other_set)
    intersection_update.__doc__ = set.intersection_update.__doc__
    __iand__ = intersection_update

    def pop(self, elem):
        self._tell_change()
        set.pop(self, elem)
    pop.__doc__ = set.pop.__doc__

    def remove(self, elem):
        self._tell_change()
        set.remove(self, elem)
    remove.__doc__ = set.remove.__doc__

    def symmetric_difference_update(self, other_set):
        self._tell_change()
        set.symmetric_difference_update(self, other_set)
    symmetric_difference_update.__doc__ = set.symmetric_difference_update.__doc__
    __ixor__ = symmetric_difference_update

    def update(self, other_set):
        self._tell_change()
        set.update(self, other_set)
    update.__doc__ = set.update.__doc__

    def _tell_change(self):
        self._server_obj._save_old_value(self._attr_name)

def _format_value(value):
    if not value:
        return ''
    elif value is NonExistingAttribute:
        return '(does not exist)'
    elif isinstance(value, set):
        return ', '.join(value)
    else:
        return value
