from adminapi import BASE_URL, _api_settings
from adminapi.utils import IP
from adminapi.request import send_request
from adminapi.dataset.base import BaseQuerySet, BaseServerObject, \
        DatasetException, NonExistingAttribute, MultiAttr
from adminapi.dataset.filters import _prepare_filter

COMMIT_URL = BASE_URL + '/dataset/commit'
QUERY_URL = BASE_URL + '/dataset/query'

class QuerySet(BaseQuerySet):
    def __init__(self, filters, auth_token):
        BaseQuerySet.__init__(self, filters)
        self.auth_token = auth_token
        self.attributes = {}

    def __repr__(self):
        # QuerySet is not used directly but through query function
        kwargs = ', '.join('{0}={1!r}'.format(k, v) for k, v in
                self._filters.iteritems())
        query_repr = 'query({0})'.format(kwargs)
        if self._restrict:
            query_repr += '.restrict({0})'.format(', '.join(self._restrict))
        return query_repr

    def augment(self, *attrs):
        raise NotImplementedError('Augmenting is not available yet!')

    def commit(self):
        raise NotImplementedError("Committing is not available yet!")
        commit = {
            'deleted': [],
            'changes': {}
        }
        for obj in self:
            if obj.is_deleted():
                commit['deleted'].append(obj.object_id)
            elif obj.is_dirty():
                commit['changes'][obj.object_id] = obj._serialize_changes()
        
        result = send_request(COMMIT_URL, commit, self.auth_token)

        if result['status'] == 'success':
            self.num_dirty = 0
            for obj in self:
                obj._confirm_changes()
            return True
        else:
            raise DatasetException(result['exception_msg'])

    def count(self):
        return 1

    def _fetch_results(self):
        serialized_filters = dict((k, v._serialize()) for k, v in
                self._filters.iteritems())
        
        request_data = {
            'filters': serialized_filters,
            'restrict': self._restrict,
            'augmentations': self._augmentations
        }
        result = send_request(QUERY_URL, request_data, self.auth_token)
        if result['status'] == 'success':
            self.attributes = result['attributes']
            # The attributes in convert_set must be converted to sets
            # and attributes in convert_ip musst be converted to ips
            convert_set = frozenset(attr_name for attr_name, attr in
                    self.attributes.iteritems() if attr['multi'])
            convert_ip = frozenset(attr_name for attr_name, attr in
                    self.attributes.iteritems() if attr['type'] == 'ip')
            servers = {}
            for object_id, server in result['servers'].iteritems():
                object_id = int(object_id)
                server_obj = ServerObject(object_id, self, self.auth_token)
                for attr in convert_set:
                    if attr not in server:
                        continue
                    if attr in convert_ip:
                        server[attr] = MultiAttr((IP(x) for x in server[attr]),
                                server_obj, attr)
                    else:
                        server[attr] = MultiAttr(server[attr], server_obj, attr)
                for attr in convert_ip:
                    if attr not in server or attr in convert_set:
                        continue
                    server[attr] = IP(server[attr])
                dict.update(server_obj, server)
                servers[object_id] = server_obj
            return servers
        else:
            raise DatasetException(result['exception_msg'])

class ServerObject(BaseServerObject):
    def __init__(self, object_id=None, queryset=None, auth_token=None):
        BaseServerObject.__init__(self, None, object_id, queryset)
        self.auth_token = auth_token

    def _serialize_changes(self):
        changes = {}
        for key, old_value in self.old_values.iteritems():
            new_value = self.get(key, NonExistingAttribute)
            old_plain = old_value if old_value != NonExistingAttribute else None
            new_plain = new_value if new_value != NonExistingAttribute else None
            changes[key] = {
                'old': old_plain,
                'new': new_plain,
                'is_del': new_value == NonExistingAttribute,
                'is_new': old_value == NonExistingAttribute
            }
        return changes

    def commit(self):
        raise NotImplementedError("Committing is not available yet!")

def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.iteritems())
    return QuerySet(filters=filters, auth_token=_api_settings['auth_token'])
