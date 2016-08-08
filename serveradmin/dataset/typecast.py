import re
from datetime import datetime
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address

from django.core.exceptions import ValidationError

_to_datetime_re = re.compile(
    r'(\d{4})-(\d{1,2})-(\d{1,2})(T(\d{1,2}):(\d{1,2})(:(\d{1,2}))?)?'
)


def _to_datetime(x):

    if isinstance(x, datetime):
        return x

    if isinstance(x, (int, long)):
        return datetime.fromtimestamp(x)

    if isinstance(x, basestring):
        if x.isdigit():
            return datetime.fromtimestamp(int(x))

        match = _to_datetime_re.match(x)
        if not match:
            raise ValidationError('Could not cast {0!r} to datetime'.format(x))

        hour, minute, second = 0, 0, 0
        if match.group(5):
            hour = int(match.group(5))
            minute = int(match.group(6))
        if match.group(8):
            second = int(match.group(8))

        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            hour,
            minute,
            second,
        )

    raise ValidationError('Could not cast {0!r} to datetime', x)

_hex_sep = '([a-fA-F0-9]{,2})[^a-fA-Z0-9]'
_mac_re = re.compile('^' + _hex_sep * 5 + '([a-fA-F0-9]{,2})$')
_mac_re_nosep = re.compile('^[a-fA-F0-9]{12}$')


def _to_mac(mac):

    match = _mac_re.match(mac)
    if match:
        parts = [match.group(grp).lower().zfill(2) for grp in xrange(1, 7)]
        return u':'.join(parts)

    if _mac_re_nosep.match(mac):
        mac_lower = mac.lower()
        return u':'.join(mac_lower[i:i+2] for i in xrange(6))

    raise ValidationError(u'Invalid MAC "{0}"'.format(mac))

_typecast_fns = {
    'integer': int,
    'boolean': lambda x: x in ('1', 'True', 'true', 1, True),
    'string': lambda x: x if isinstance(x, basestring) else unicode(x),
    'ip': lambda x: x if isinstance(x, IPv4Address) else IPv4Address(x),
    'ipv6': lambda x: x if isinstance(x, IPv6Address) else IPv6Address(x),
    'datetime': _to_datetime,
    'mac': _to_mac,
    'hostname': str,
    'reverse_hostname': str,
    'number': Decimal,
}


def typecast(attribute, value, force_single=False):
    if value is None:
        return value

    typecast_fn = _typecast_fns[attribute.type]

    if attribute.multi and not force_single:
        if not isinstance(value, (list, set)):
            raise ValidationError('Attr is multi, but value is not a list/set')

        return set(typecast_fn(x) for x in value)

    try:
        return typecast_fn(value)
    except ValueError as error:
        raise ValidationError(str(error))

_displaycast_fns = {
    'datetime': lambda x: x.strftime('%Y-%m-%dT%H:%M'),
    'boolean': lambda x: u'true' if x else u'false',
}


def displaycast(attribute, value):

    displaycast_fn = _displaycast_fns.get(attribute.type, lambda x: x)

    if attribute.multi:
        if not isinstance(value, (list, set)):
            raise ValidationError('Attr is multi, but value is not a list/set')

        result = [displaycast_fn(x) for x in value]
        result.sort()

        return result

    return displaycast_fn(value)
