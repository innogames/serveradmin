import json

from adminapi import BASE_URL, _api_settings
from adminapi.request import send_request
from adminapi.dataset.base import BaseQuerySet, BaseServerObject, \
        DatasetException, NonExistingAttribute
from adminapi.dataset.filters import _prepare_filter

COMMIT_URL = BASE_URL + '/dataset/commit'
REQUEST_URL = BASE_URL + '/dataset/request'

class QuerySet(BaseQuerySet):
    def __init__(self, filters, auth_token):
        BaseQuerySet.__init__(self, filters)
        self.auth_token = auth_token

    def __repr__(self):
        # QuerySet is not used directly but through query function
        kwargs = ', '.join('{0}={1!r}'.format(k, v) for k, v in
                self.filters.iteritems())
        return 'query({0})'.format(kwargs)

    def commit(self):
        commit = {
            'deleted': [],
            'changes': {}
        }
        for obj in self:
            if obj.is_deleted():
                commit['deleted'].append(obj.object_id)
            elif obj.is_dirty():
                commit[obj.object_id] = obj._serialize_changes()
        
        result_json = send_request(COMMIT_URL, commit, self.auth_token)
        result = json.loads(result_json)

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
        
        request_data = json.dumps({
            'filters': serialized_filters,
            'restrict': self._restrict,
            'augmentations': self._augmentations
        })
        result_json = send_request(REQUEST_URL, request_data, self.auth_token)
        result = json.loads(result_json)
        
        if result['status'] == 'success':
            # The attributes in convert_set must be converted to sets
            convert_set = result['convert_set']
            servers = {}
            for server in result['servers']:
                object_id = int(server['object_id'])
                del server['object_id']
                for attr in convert_set:
                    server[attr] = set(server[attr])
                servers[object_id] = ServerObject(server, object_id, self,
                        self.auth_token)
            return servers
        else:
            raise DatasetException(result['exception_msg'])

class ServerObject(BaseServerObject):
    def __init__(self, attributes, object_id=None, queryset=None,
                 auth_token=None):
        BaseServerObject.__init__(self, attributes, object_id, queryset)
        self.auth_token = auth_token

    def _serialize_changes(self):
        changes = {}
        for key, old_value in self.old_values:
            new_value = self.get(key, NonExistingAttribute)
            old_plain = old_value if old_value != NonExistingAttribute else None
            new_plain = new_value if new_value != NonExistingAttribute else None
            changes[key] = {
                'old_value': old_plain,
                'new_value': new_plain,
                'deleted': new_value == NonExistingAttribute,
                'new': old_value == NonExistingAttribute
            }
        return changes

    def commit(self):
        pass

def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.iteritems)
    return QuerySet(filters=filters, auth_token=_api_settings['auth_token'])
