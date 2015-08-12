from time import mktime
from datetime import datetime, date, timedelta

from adminapi.utils import IP, IPv6, Network

def json_encode_extra(obj):
    # Proxied sets are used by MultiAttr
    if hasattr(obj, '_proxied_set'):
        return list(obj._proxied_set)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, IP):
        return obj.ip
    elif isinstance(obj, IPv6):
        return obj.as_ip()
    elif isinstance(obj, Network):
        return [obj.min_ip, obj.max_ip]
    elif isinstance(obj, (datetime, date)):
        return int(mktime(obj.timetuple()))
    elif isinstance(obj, timedelta):
        return obj.seconds + obj.days * 24 * 3600
    raise TypeError('Type ' + str(type(obj)) + ' is not known')
