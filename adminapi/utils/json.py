from time import mktime
from datetime import datetime, date, timedelta

def json_encode_extra(obj):

    # Proxied sets are used by MultiAttr
    if hasattr(obj, '_proxied_set'):
        return list(obj._proxied_set)

    if isinstance(obj, set):
        return list(obj)

    if isinstance(obj, (datetime, date)):
        return int(mktime(obj.timetuple()))

    if isinstance(obj, timedelta):
        return obj.seconds + obj.days * 24 * 3600

    return str(obj)
