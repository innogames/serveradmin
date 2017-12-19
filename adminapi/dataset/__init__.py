from adminapi.base import (
    BaseQuery, BaseServerObject, DatasetError, MultiAttr, json_to_datatype
)
from adminapi.filters import BaseFilter
from adminapi.request import send_request

COMMIT_ENDPOINT = '/dataset/commit'
QUERY_ENDPOINT = '/dataset/query'
CREATE_ENDPOINT = '/dataset/create'


class Attribute(object):
    def __init__(self, name, type, multi):  # NOQA A002
        self.name = name
        self.type = type
        self.multi = multi


class Query(BaseQuery):
    def __init__(self, filters):
        self._filters = {
            a: f if isinstance(f, BaseFilter) else BaseFilter(f)
            for a, f in filters.items()
        }
        self._results = None
        self._restrict = None
        self._order_by = None

    def commit(self, skip_validation=False, force_changes=False):
        commit = self._build_commit_object()
        commit['skip_validation'] = skip_validation
        commit['force_changes'] = force_changes
        result = send_request(COMMIT_ENDPOINT, commit)

        if result['status'] == 'success':
            self.num_dirty = 0
            for obj in self:
                obj._confirm_changes()
            return True
        elif result['status'] == 'error':
            _handle_exception(result)

    def get_results(self):
        if self._results is None:
            request_data = {
                'filters': self._filters,
                'restrict': self._restrict,
                'order_by': self._order_by,
            }
            response = send_request(QUERY_ENDPOINT, request_data)
            self._handle_response(response)
        return self._results

    def _handle_response(self, response):
        if response['status'] == 'success':
            self._results = []
            for server in response['result']:
                object_id = server['object_id']
                server_obj = ServerObject([], object_id)
                for attribute_id, value in list(server.items()):
                    if isinstance(value, list):
                        casted_value = MultiAttr((
                            json_to_datatype(v) for v in value
                        ), server_obj, attribute_id)
                    else:
                        casted_value = json_to_datatype(value)
                    dict.__setitem__(server_obj, attribute_id, casted_value)
                self._results.append(server_obj)

        elif response['status'] == 'error':
            _handle_exception(response)


class ServerObject(BaseServerObject):
    def commit(self, skip_validation=False, force_changes=False):
        commit = self._build_commit_object()
        commit['skip_validation'] = skip_validation
        commit['force_changes'] = force_changes
        result = send_request(COMMIT_ENDPOINT, commit)

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


# XXX Deprecated, use Query() instead
def query(**kwargs):
    return Query(kwargs)


def create(
    attributes,
    skip_validation=False,
    fill_defaults=True,
    fill_defaults_all=False,
):
    request = {
        'attributes': attributes,
        'skip_validation': skip_validation,
        'fill_defaults': fill_defaults,
        'fill_defaults_all': fill_defaults_all,
    }

    response = send_request(CREATE_ENDPOINT, request)
    qs = Query({'hostname': attributes['hostname']})
    qs._handle_response(response)

    return qs.get()
