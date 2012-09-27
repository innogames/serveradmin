import re
from datetime import datetime

from adminapi.utils import IP
from serveradmin.dataset.base import lookups

_to_datetime_re = re.compile(
        r'(\d{4})-(\d{1,2})-(\d{1,2})(T(\d{1,2}):(\d{1,2})(:(\d{1,2}))?)?')
def _to_datetime(x):
    if isinstance(x, datetime):
        return x
    if isinstance(x, (int, long)):
        return datetime.fromtimestamp(x)
    elif isinstance(x, basestring):
        if x.isdigit():
            return datetime.fromtimestamp(int(x))
        match = _to_datetime_re.match(x)
        if not match:
            raise ValueError('Could not cast {0!r} to datetime', x)

        hour, minute, second = 0, 0, 0
        if match.group(5):
            hour = int(match.group(5))
            minute = int(match.group(6))
        if match.group(8):
            second = int(match.group(8))

        return datetime(int(match.group(1)), int(match.group(2)),
                        int(match.group(3)), hour, minute, second)
    else:
        raise ValueError('Could not cast {0!r} to datetime', x)

_typecast_fns = {
    'integer': int,
    'boolean': lambda x: x in ('1', 'True', 'true', 1, True),
    'string': lambda x: x if isinstance(x, basestring) else unicode(x),
    'ip': lambda x: x if isinstance(x, IP) else IP(x),
    'datetime': _to_datetime
}
def typecast(attr_name, value):
    if value is None:
        return value
    attr_obj = lookups.attr_names[attr_name]
    typecast_fn = _typecast_fns[attr_obj.type]
    if attr_obj.multi:
        if not isinstance(value, (list, set)):
            raise ValueError('Attr is multi, but value is not a list/set')
        return set(typecast_fn(x) for x in value)
    else:
        return typecast_fn(value)
