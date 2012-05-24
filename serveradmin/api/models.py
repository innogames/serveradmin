from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError

@api_function(group='debug')
def echo(*args, **kwargs):
    """Return the given positional and keyword arguments"""
    return {
        'args': args,
        'kwargs': kwargs
    }

class RaiseExceptionError(ApiError):
    pass

@api_function(group='debug')
def raise_exception():
    raise RaiseExceptionError('Test exception')
