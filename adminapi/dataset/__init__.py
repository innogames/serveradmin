from ipaddress import ip_address, ip_network

from adminapi import _api_settings
from adminapi.request import send_request
from adminapi.dataset.base import BaseQuerySet, BaseServerObject, DatasetError
from adminapi.dataset.filters import _prepare_filter

COMMIT_ENDPOINT = '/dataset/commit'
QUERY_ENDPOINT = '/dataset/query'
CREATE_ENDPOINT = '/dataset/create'


class Attribute(object):
    def __init__(self, name, type, multi):
        self.name = name
        self.type = type
        self.multi = multi


class QuerySet(BaseQuerySet):
    def __init__(self, filters, auth_token, timeout):
        BaseQuerySet.__init__(self, filters)
        self.auth_token = auth_token
        self.attributes = {}
        self.timeout = timeout

    def augment(self, *attrs):
        raise NotImplementedError('Augmenting is not available yet!')

    def commit(self, skip_validation=False, force_changes=False):
        commit = self._build_commit_object()
        commit['skip_validation'] = skip_validation
        commit['force_changes'] = force_changes
        result = send_request(COMMIT_ENDPOINT, commit, self.auth_token,
                              self.timeout)

        if result['status'] == 'success':
            self.num_dirty = 0
            for obj in self:
                obj._confirm_changes()
            return True
        elif result['status'] == 'error':
            _handle_exception(result)

    def count(self):
        return len(self)

    def _fetch_results(self):
        serialized_filters = dict(
            (k, v._serialize()) for k, v in self._filters.items()
        )
        request_data = {
            'filters': serialized_filters,
            'restrict': self._restrict,
            'augmentations': self._augmentations,
        }
        result = send_request(QUERY_ENDPOINT, request_data, self.auth_token,
                              self.timeout)
        return self._handle_result(result)

    def _handle_result(self, result):
        if result['status'] == 'success':
            attributes = {}
            for attr_name, attr in result['attributes'].items():
                attributes[attr_name] = Attribute(
                    attr_name, attr['type'], attr['multi']
                )
            self.attributes = attributes
            # The attributes in convert_set must be converted to sets
            # and attributes in convert_ip must be converted to ips
            convert_set = frozenset(
                attr_name for attr_name, attr in self.attributes.items()
                if attr.multi
            )
            convert_ip = frozenset(
                attr_name for attr_name, attr in self.attributes.items()
                if attr.type in ('ip', 'inet')
            )
            self._results = {}
            for object_id, server in result['servers'].items():
                object_id = int(object_id)
                server_obj = ServerObject(object_id, self, self.auth_token,
                                          self.timeout)
                for attr in convert_set:
                    if attr not in server:
                        continue
                    if attr in convert_ip:
                        server[attr] = set(
                            ip_network(x) if '/' in x else ip_address(x)
                            for x in server[attr]
                        )
                    else:
                        server[attr] = set(server[attr])
                for attr in convert_ip:
                    if server.get(attr) is None or attr in convert_set:
                        continue
                    if '/' in server[attr]:
                        server[attr] = ip_network(server[attr])
                    else:
                        server[attr] = ip_address(server[attr])
                dict.update(server_obj, server)
                self._results[object_id] = server_obj

        elif result['status'] == 'error':
            _handle_exception(result)


class ServerObject(BaseServerObject):
    def __init__(self, object_id=None, queryset=None, auth_token=None,
                 timeout=None):
        BaseServerObject.__init__(self, None, object_id, queryset)
        self.auth_token = auth_token
        self.timeout = timeout

    def commit(self, skip_validation=False, force_changes=False):
        commit = self._build_commit_object()
        commit['skip_validation'] = skip_validation
        commit['force_changes'] = force_changes
        result = send_request(COMMIT_ENDPOINT, commit, self.auth_token,
                              self.timeout)

        if result['status'] == 'success':
            self._confirm_changes()
            return True
        elif result['status'] == 'error':
            _handle_exception(result)


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


def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.items())
    return QuerySet(
        filters=filters,
        auth_token=_api_settings['auth_token'],
        timeout=_api_settings['timeout_dataset'],
    )


def create(
    attributes,
    skip_validation=False,
    fill_defaults=True,
    fill_defaults_all=False,
    auth_token=None,
):
    request_data = {
        'attributes': attributes,
        'skip_validation': skip_validation,
        'fill_defaults': fill_defaults,
        'fill_defaults_all': fill_defaults_all,
    }

    if auth_token is None:
        auth_token = _api_settings['auth_token']

    result = send_request(CREATE_ENDPOINT, request_data, auth_token,
                          _api_settings['timeout_dataset'])
    qs = QuerySet(
        filters={'hostname': _prepare_filter(attributes['hostname'])},
        auth_token=auth_token,
        timeout=_api_settings['timeout_dataset'],
    )
    qs._handle_result(result)

    return qs.get()
