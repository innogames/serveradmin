import time
from datetime import datetime

from django.db import connection

from adminapi.utils import IP, IPv6
from serveradmin.dataset.base import lookups

def _sql_escape(value):

    if isinstance(value, basestring):
        return raw_sql_escape(value)

    if isinstance(value, (int, long, float)):
        return unicode(value)

    if isinstance(value, bool):
        return u'1' if value else u'0'

    if isinstance(value, datetime):
        return unicode(time.mktime(value.timetuple()))

    raise ValueError(
            u'Value of type {0} can not be used in SQL'.format(value)
        )

def value_to_sql(attr_obj, value):
    return _sql_escape(prepare_value(attr_obj, value))

def prepare_value(attr_obj, value):

    # Casts by type
    if attr_obj.type == u'boolean':
        value = 1 if value else 0
    elif attr_obj.type == u'ip':
        if not isinstance(value, IP):
            value = IP(value)
        value = value.as_int()
    elif attr_obj.type == u'ipv6':
        if not isinstance(value, IPv6):
            value = IPv6(value)
        value = value.as_hex()
    elif attr_obj.type == u'datetime':
        if isinstance(value, datetime):
            value = int(time.mktime(value.timetuple()))

    # Validations of special attributes
    if attr_obj.name == u'servertype':
        if value not in lookups.stype_names:
            raise ValueError(u'Invalid servertype: ' + value)
    if attr_obj.name == u'segment':
        if value not in lookups.segments:
            raise ValueError(u'Invalid segment: ' + value)
    if attr_obj.name == u'project':
        if value not in lookups.projects:
            raise ValueError(u'Invalid project: ' + value)

    # XXX: Dirty hack for the old database structure
    if attr_obj.name == u'servertype':
        value = lookups.stype_names[value].pk

    return value

def raw_sql_escape(value):
    # escape_string just takes bytestrings, so convert unicode back and forth
    if isinstance(value, unicode):
        value = value.encode('utf-8')
    return u"'{0}'".format(connection.connection.escape_string(value).decode('utf-8'))
