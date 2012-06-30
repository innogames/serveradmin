from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError

@api_function(group='debug')
def echo(*args, **kwargs):
    """Return the given positional and keyword arguments.
    
    Example::
       
       dbg = api.get('debug')
       print dbg.echo('hello', 'world', numbers=[23, 42])
       
    """
    return {
        'args': args,
        'kwargs': kwargs
    }

class RaiseExceptionError(ApiError):
    pass

@api_function(group='debug')
def raise_exception():
    """Just raise an exception of type ``RaiseExceptionError``.
    
    Example::
       
       dbg = api.get('debug')
       try:
           result = dbg.raise_exception()
       except api.exc.RaiseExceptionError:
           print 'Catched specific exception!'
       except api.exc.ApiError:
           print 'I will catch all API exceptions'
       
    """
    raise RaiseExceptionError('Test exception')
