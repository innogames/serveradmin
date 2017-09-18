from ipaddress import ip_address, ip_network

from adminapi import _api_settings
from adminapi.base import (
    BaseQuerySet, BaseServerObject, DatasetError, MultiAttr
)
from adminapi.request import send_request

COMMIT_ENDPOINT = '/dataset/commit'
QUERY_ENDPOINT = '/dataset/query'
CREATE_ENDPOINT = '/dataset/create'


class Attribute(object):
    def __init__(self, name, type, multi):  # NOQA A002
        self.name = name
        self.type = type
        self.multi = multi


class QuerySet(BaseQuerySet):
    def __init__(self, filters, auth_token, timeout):
        BaseQuerySet.__init__(self, filters)
        self.auth_token = auth_token
        self.timeout = timeout

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

    def _fetch_results(self):
        request_data = {
            'filters': self._filters,
            'restrict': self._restrict,
            'order_by': self._order_by,
        }
        response = send_request(
            QUERY_ENDPOINT, request_data, self.auth_token, self.timeout
        )
        return self._handle_response(response)

    def _handle_response(self, response):
        if response['status'] == 'success':
            self._results = []
            for server in response['result']:
                object_id = server['object_id']
                server_obj = ServerObject(
                    object_id, self, self.auth_token, self.timeout
                )
                for attribute_id, value in list(server.items()):
                    if isinstance(value, list):
                        server[attribute_id] = MultiAttr(
                            server[attribute_id], server_obj, attribute_id
                        )
                    elif (
                        attribute_id in ServerObject.inet_attribute_ids and
                        server[attribute_id]
                    ):
                        server[attribute_id] = (
                            ip_network(server[attribute_id])
                            if '/' in server[attribute_id]
                            else ip_address(server[attribute_id])
                        )
                dict.update(server_obj, server)
                self._results.append(server_obj)

        elif response['status'] == 'error':
            _handle_exception(response)


class ServerObject(BaseServerObject):

    # TODO: Query the datatypes once from the server
    inet_attribute_ids = {'intern_ip', 'primary_ip6'}

    def __init__(self, object_id=None, queryset=None, auth_token=None,
                 timeout=None):
        BaseServerObject.__init__(self, [], object_id, queryset)
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
    return QuerySet(
        filters=kwargs,
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
    request = {
        'attributes': attributes,
        'skip_validation': skip_validation,
        'fill_defaults': fill_defaults,
        'fill_defaults_all': fill_defaults_all,
    }

    if auth_token is None:
        auth_token = _api_settings['auth_token']

    response = send_request(
        CREATE_ENDPOINT, request, auth_token, _api_settings['timeout_dataset']
    )
    qs = QuerySet(
        filters={'hostname': attributes['hostname']},
        auth_token=auth_token,
        timeout=_api_settings['timeout_dataset'],
    )
    qs._handle_response(response)

    return qs.get()
