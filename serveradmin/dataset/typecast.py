import re
from datetime import datetime

from adminapi.utils import IP, IPv6
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
            raise ValueError('Could not cast {0!r} to datetime'.format(x))

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

_hex_sep = '([a-fA-F0-9]{,2})[^a-fA-Z0-9]'
_mac_re = re.compile('^' + _hex_sep * 5 + '([a-fA-F0-9]{,2})$')
_mac_re_nosep = re.compile('^[a-fA-F0-9]{12}$')
def _to_mac(mac):
    match = _mac_re.match(mac)
    if match:
        parts = [match.group(grp).lower().zfill(2) for grp in xrange(1, 7)]
        return u':'.join(parts)
    elif _mac_re_nosep.match(mac):
        mac_lower = mac.lower()
        return u':'.join(mac_lower[i:i+2] for i in xrange(6))
    else:
        raise ValueError(u'Invalid MAC "{0}"'.format(mac))


_typecast_fns = {
    'integer': int,
    'boolean': lambda x: x in ('1', 'True', 'true', 1, True),
    'string': lambda x: x if isinstance(x, basestring) else unicode(x),
    'ip': lambda x: x if isinstance(x, IP) else IP(x),
    'ipv6': lambda x: x if isinstance(x, IPv6) else IPv6(x),
    'datetime': _to_datetime,
    'mac': _to_mac
}
def typecast(attr_name, value, force_single=False):
    if value is None:
        return value
    attr_obj = lookups.attr_names[attr_name]
    typecast_fn = _typecast_fns[attr_obj.type]
    if attr_obj.multi and not force_single:
        if not isinstance(value, (list, set)):
            raise ValueError('Attr is multi, but value is not a list/set')
        return set(typecast_fn(x) for x in value)
    else:
        return typecast_fn(value)
