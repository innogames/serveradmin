from adminapi import _api_settings
from adminapi.request import send_request

API_CALL_ENDPOINT = '/call'

class ApiError(Exception):
    pass

class ExceptionManager(object):
    def __init__(self):
        self._cache = {}

    def __getattr__(self, attr):
        if attr == 'ApiError':
            return ApiError

        if attr not in self._cache:
            exc = type(attr, (ApiError, ), {})
            self._cache[attr] = exc

        return self._cache[attr]

class FunctionGroup(object):
    def __init__(self, group, auth_token, timeout):
        self.group = group
        self.auth_token = auth_token
        self.timeout = timeout

    def __getattr__(self, attr):
        def _api_function(*args, **kwargs):
            call = {
                    'group': self.group,
                    'name': attr,
                    'args': args,
                    'kwargs': kwargs,
                }

            if hasattr(self.auth_token, '__call__'):
                self.auth_token = self.auth_token()

            result = send_request(API_CALL_ENDPOINT, call, self.auth_token,
                                  self.timeout)

            if result['status'] == 'success':
                return result['retval']

            if result['status'] == 'error':

                if result['type'] == 'ValueError':
                    exception_class = ValueError
                elif result['type'] == 'TypeError':
                    exception_class = TypeError
                else:
                    exception_class = getattr(ExceptionManager(), result['type'])

                #
                # Dear traceback reader,
                #
                # This is not the location of the exception, please read the
                # exception message and figure out what's wrong with your
                # code.
                #
                raise exception_class(result['message'])

        return _api_function

def get(group):
    # We allow delaying the authentication
    if _api_settings['auth_token'] is None:
        token = lambda: _api_settings['auth_token']
    else:
        token = _api_settings['auth_token']

    return FunctionGroup(group, token, _api_settings['timeout_api'])
