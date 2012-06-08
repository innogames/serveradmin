from time import mktime
from datetime import datetime, date, timedelta

from adminapi.dataset.base import MultiAttr
from adminapi.utils import IP

def json_encode_extra(obj):
    if isinstance(obj, MultiAttr):
        return list(obj._proxied_set)
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, IP):
        return obj.ip
    elif isinstance(obj, (datetime, date)):
        return int(mktime(obj.timetuple()))
    elif isinstance(obj, timedelta):
        return obj.seconds + obj.days * 24 * 3600
    raise TypeError()
