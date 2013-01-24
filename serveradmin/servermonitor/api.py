from serveradmin.api.decorators import api_function
from serveradmin.api import ApiError

from serveradmin.servermonitor.models import ServermonitorError, get_rrd_data

@api_function(group='servermonitor')
def get_rrd_values(create_definition, hostname, df='AVERAGE', start=None,
                   stop=None, aggregate=None):
    """Return a dictionary of values in the RRD files.
    
    This looks like the following one::

       {
        'de13l1.gp': {
                      'start': 1358862600,
                      'stop': 1358863500,
                      'step': 300,
                      'data': {
                               'load1': [0.0, 0.7, 20.3, 17.2, None, 13.2],
                               'load5': [1.0, 3.2, 15.3, 19.2, None, 7.2],
                              }
                     },
       }

    You will get multiple hosts if the create definition is of the type dom0.

    If start and stop (unix timestamp) is given, the number of results will
    be restricted to the given interval.

    If an aggregate function ('sum' or 'avg') is given, you will get only
    one value instead of a list of values.
    """
    
    try:
        return get_rrd_data(create_definition, hostname, df, start, stop,
                aggregate)
    except ServermonitorError, e:
        raise ApiError(unicode(e))

