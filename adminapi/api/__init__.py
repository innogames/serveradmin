from adminapi import BASE_URL, _api_settings
from adminapi.request import send_request

API_CALL_URL = BASE_URL + '/call'

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
exc = ExceptionManager()

class FunctionGroup(object):
    def __init__(self, group, auth_token):
        self.group = group
        self.auth_token = auth_token
    
    def __getattr__(self, attr):
        def _api_function(*args, **kwargs):
            call = {
                'group': self.group,
                'name': attr,
                'args': args,
                'kwargs': kwargs
            }
            result = send_request(API_CALL_URL, call, self.auth_token)

            if result['status'] == 'success':
                return result['retval']
            elif result['status'] == 'error':
                exception_class = {
                    'ValueError': ValueError,
                    'TypeError': TypeError
                }.get(result['type'], getattr(exc, result['type']))
                # Dear traceback reader,
                # this is not the location of the exception, please read the
                # exception message and figure out what's wrong with your code
                raise exception_class(result['message'])

        return _api_function


def get(group):
    return FunctionGroup(group, _api_settings['auth_token'])

