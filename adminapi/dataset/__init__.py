from adminapi import BASE_URL, _api_settings
from adminapi.utils import IP
from adminapi.request import send_request
from adminapi.dataset.base import BaseQuerySet, BaseServerObject
from adminapi.dataset.filters import _prepare_filter
from adminapi.dataset.exceptions import (DatasetError, CommitError, 
        CommitValidationFailed, CommitNewerData) # Import into this Namespace

COMMIT_URL = BASE_URL + '/dataset/commit'
QUERY_URL = BASE_URL + '/dataset/query'
CREATE_URL = BASE_URL + '/dataset/create'

class Attribute(object):
    def __init__(self, name, type, multi):
        self.name = name
        self.type = type
        self.multi = multi

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
        commit = self._build_commit_object() 
        result = send_request(COMMIT_URL, commit, self.auth_token)

        if result['status'] == 'success':
            self.num_dirty = 0
            for obj in self:
                obj._confirm_changes()
            return True
        elif result['status'] == 'error':
            _handle_exception(result)

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
        return self._handle_result(result)

    def _handle_result(self, result):
        if result['status'] == 'success':
            attributes = {}
            for attr_name, attr in result['attributes'].iteritems():
                attributes[attr_name] = Attribute(attr_name, attr['type'],
                        attr['multi'])
            self.attributes = attributes
            # The attributes in convert_set must be converted to sets
            # and attributes in convert_ip musst be converted to ips
            convert_set = frozenset(attr_name for attr_name, attr in
                    self.attributes.iteritems() if attr.multi)
            convert_ip = frozenset(attr_name for attr_name, attr in
                    self.attributes.iteritems() if attr.type == 'ip')
            servers = {}
            for object_id, server in result['servers'].iteritems():
                object_id = int(object_id)
                server_obj = ServerObject(object_id, self, self.auth_token)
                for attr in convert_set:
                    if attr not in server:
                        continue
                    if attr in convert_ip:
                        server[attr] = set(IP(x) for x in server[attr])
                    else:
                        server[attr] = set(server[attr])
                for attr in convert_ip:
                    if attr not in server or attr in convert_set:
                        continue
                    server[attr] = IP(server[attr])
                dict.update(server_obj, server)
                servers[object_id] = server_obj
            return servers
        elif result['status'] == 'error':
            exception_class = {
                'ValueError': ValueError
            }.get(result['type'], DatasetError)
            raise exception_class(result['message'])


class ServerObject(BaseServerObject):
    def __init__(self, object_id=None, queryset=None, auth_token=None):
        BaseServerObject.__init__(self, None, object_id, queryset)
        self.auth_token = auth_token

    def commit(self):
        commit = self._build_commit_object() 
        result = send_request(COMMIT_URL, commit, self.auth_token)

        if result['status'] == 'success':
            self._confirm_changes()
            return True
        elif result['status'] == 'error':
            _handle_exception(result)

def _handle_exception(result):
    exception_class = {
        'ValueError': ValueError
    }.get(result['type'], DatasetError)
    # Dear traceback reader,
    # this is not the location of the exception, please read the
    # exception message and figure out what's wrong with your code
    raise exception_class(result['message'])


def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.iteritems())
    return QuerySet(filters=filters, auth_token=_api_settings['auth_token'])

def create(attributes, skip_validation=False, fill_defaults=True,
        fill_defaults_all=False, auth_token=None):
    
    request_data = {
        'attributes': attributes,
        'skip_validation': skip_validation,
        'fill_defaults': fill_defaults,
        'fill_defaults_all': fill_defaults_all
    }

    if auth_token is None:
        auth_token = _api_settings['auth_token']

    result = send_request(CREATE_URL, request_data, auth_token)
    qs = QuerySet(filters={'hostname': _prepare_filter(attributes['hostname'])},
            auth_token=auth_token)
    qs._handle_result(result)
    return qs.get()
