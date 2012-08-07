import random

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

@api_function(group='debug')
def raise_random_exception(*names):
    """Raise a random exception.

    It will make up exceptions from the given names and choose on of
    them at random -- or a completely different exception.
    """
    
    names.append(None)
    name = random.choice(names)

    if not name:
        name = 'code{0}'.format(random.randint(1000, 9999))
    exc_name = '{0}Error'.format(name.capitalize())

    raise type(exc_name, (ApiError, ), {})
