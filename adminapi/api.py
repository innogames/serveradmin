"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

from adminapi.request import send_request
from adminapi.exceptions import ApiError

API_CALL_ENDPOINT = '/call'


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

            result = send_request(API_CALL_ENDPOINT, post_params=call)

            if result['status'] == 'error':
                raise ApiError(result['message'], status_code=None)

            return result['retval']

        return _api_function


# XXX Deprecated
def get(group):
    return FunctionGroup(group)
