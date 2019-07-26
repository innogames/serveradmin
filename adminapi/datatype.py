"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""
from datetime import date, datetime
from re import compile as re_compile
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

from netaddr import EUI
try:
    from netaddr import mac_unix_expanded
except ImportError:
    from netaddr import mac_unix as mac_unix_expanded

from adminapi.exceptions import DatatypeError


# We use a set of regular expressions to cast to datatypes.  This module
# is not aware of the attributes types of the server, neither it tries
# to match with them one to one.  Its purpose is to provide convenience
# to the user.  A string must not match with multiple expressions, or
# anything that can be reasonably used as a string attribute.  Therefore,
# they are not specified to cover broad range of inputs, but the cover
# the way the server returns such types.
RE_32 = r'([0-9]|[1-2][0-9]|3[0-2])'
RE_128 = r'([0-9]|[1-9][0-9]|1(1[0-9]|2[0-8]))'
RE_255 = r'([0-9]|[1-9][0-9]|1[0-9]{2}|2([0-4][0-9]|5[0-5]))'
RE_IPV4ADDR = r'(' + RE_255 + r'\.){3}' + RE_255
RE_IPV6ADDR = (
    r'('
    r'([0-9a-f]{1,4}:){7,7}[0-9a-f]{1,4}|'
    r'([0-9a-f]{1,4}:){1,7}:|'
    r'([0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}|'
    r'([0-9a-f]{1,4}:){1,5}(:[0-9a-f]{1,4}){1,2}|'
    r'([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,3}|'
    r'([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}|'
    r'([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}|'
    r'[0-9a-f]{1,4}:((:[0-9a-f]{1,4}){1,6})|'
    r':((:[0-9a-f]{1,4}){1,7}|:)'
    r')'
)
RE_MACADDR = r'([0-9a-f]{1,2}:){5}([0-9a-f]{1,2})'
RE_DATE = r'[0-9]{1,4}-(0[0-9]|1[0-2])-([0-2][0-9]|3[0-1])'
RE_DATETIME = RE_DATE + (
    # e.g. ' 14:11:21+0100'
    r' ([0-1][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\+|-)[0-9]{4}'
)
STR_BASED_DATATYPES = [
    (IPv4Address, re_compile(r'\A' + RE_IPV4ADDR + r'\Z')),
    (IPv4Network, re_compile(r'\A' + RE_IPV4ADDR + r'\/' + RE_32 + r'\Z')),
    (IPv6Address, re_compile(r'\A' + RE_IPV6ADDR + r'\Z')),
    (IPv6Network, re_compile(r'\A' + RE_IPV6ADDR + r'\/' + RE_128 + r'\Z')),
    (EUI, re_compile(r'\A' + RE_MACADDR + r'\Z')),
    (date, re_compile(r'\A' + RE_DATE + r'\Z')),
    (datetime, re_compile(r'\A' + RE_DATETIME + r'\Z')),
]


# TODO: Improve this using the datatype list
def validate_value(value, datatype=None):
    """It accepts an optional datatype to validate the values.  The values
    are not necessarily be an instance of this datatype.  They will be checked
    for a common super-class.  The function returns the found super-class,
    so that callers can save and reuse it.  When the datatype is not
    provided, then it will return the class of the value.

    The reason behind this method is to preserve the datatype as much as
    possible without being too strict.  Just getting the top level class
    on the inheritance tree after "object" would increase the errors, because
    with multi-inheritance there can be different top level classes.
    Therefore, this method is not really deterministic.  It can cause
    unexpected behavior, but it is the best we can do without knowing about
    the datatypes of the attributes.
    """

    special_datatypes = (
        type,
        bool,
        tuple,
        list,
        set,
        frozenset,
        dict,
        BaseException,
        type(None),
    )
    assert datatype not in special_datatypes
    if isinstance(value, special_datatypes):
        raise DatatypeError('Value cannot be from {}'.format(type(value)))

    assert datatype != object
    if type(value) == object:
        raise DatatypeError('Value cannot be a generic object')

    newtype = type(value)
    if datatype is None or issubclass(datatype, newtype):
        return newtype

    for supertype in datatype.mro():
        if issubclass(newtype, supertype) and supertype != object:
            return supertype

    raise DatatypeError(
        'Value from {} is not compatible with existing value from {}'
        .format(type(value), datatype)
    )


def str_to_datatype(value):
    if value == 'true':
        return True
    if value == 'false':
        return False
    if value.isdigit():
        return int(value)
    if all(a.isdigit() for a in value.split('.', 1)):
        return float(value)
    return json_to_datatype(value)


def json_to_datatype(value):
    for datatype, regexp in STR_BASED_DATATYPES:
        if regexp.match(str(value)):
            # date constructors need a decode format
            if datatype is date:
                return datetime.strptime(value, "%Y-%m-%d").date()
            if datatype is datetime:
                return datetime.strptime(value, '%Y-%m-%d %H:%M:%S%z')

            # EUI class represents MAC addresses in minus separated format
            # by default.  We want colon separated for for 2 reasons.
            # First, it is way more popular among the systems we care about.
            # Second, it is the format we store the addresses on the database.
            # Sometimes we pass things without casting to EUI and expect
            # the outputs to match.
            if datatype is EUI:
                return EUI(value, dialect=mac_unix_expanded)
            return datatype(value)
    return value
