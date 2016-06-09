from time import mktime
from datetime import datetime, date, timedelta


def json_encode_extra(obj):
    if isinstance(obj, set):
        return list(obj)

    if isinstance(obj, (datetime, date)):
        return int(mktime(obj.timetuple()))

    if isinstance(obj, timedelta):
        return obj.seconds + obj.days * 24 * 3600

    return str(obj)
