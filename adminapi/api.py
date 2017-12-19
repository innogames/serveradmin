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
    def __init__(self, group):
        self.group = group

    def __getattr__(self, attr):
        def _api_function(*args, **kwargs):
            call = {
                'group': self.group,
                'name': attr,
                'args': args,
                'kwargs': kwargs,
            }

            result = send_request(API_CALL_ENDPOINT, call)

            if result['status'] == 'success':
                return result['retval']

            if result['status'] == 'error':

                if result['type'] == 'ValueError':
                    exception_class = ValueError
                elif result['type'] == 'TypeError':
                    exception_class = TypeError
                else:
                    exception_class = getattr(
                        ExceptionManager(), result['type']
                    )

                #
                # Dear traceback reader,
                #
                # This is not the location of the exception, please read the
                # exception message and figure out what's wrong with your
                # code.
                #
                raise exception_class(result['message'])

        return _api_function


# XXX Deprecated
def get(group):
    return FunctionGroup(group)
