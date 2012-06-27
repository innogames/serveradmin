import re
import uuid
from threading import local
from itertools import chain
from collections import namedtuple

from django.db import connection
from django.core.cache import cache
from django.core.signals import request_started

from serveradmin.dataset.models import Attribute, ServerType

lookups = local()
ServerTypeAttr = namedtuple('ServerTypeAttr', ['servertype_id', 'attribute_id',
        'required', 'default', 'regexp', 'visible'])

class AdminTableSpecial(object):
    def __init__(self, field):
        self.field = field

class CombinedSpecial(object):
    def __init__(self, *attrs):
        self.attrs = attrs

def _read_lookups(sender=None, **kwargs):
    version = cache.get(u'dataset_lookups_version')
    if not version:
        version = uuid.uuid1().hex
        cache.add(u'dataset_lookups_version', version)

    if hasattr(lookups, u'version') and lookups.version == version:
        return
    else:
        lookups.version = version
    
    # Special attributes that don't have an entry in the attrib table
    special_attributes = [
        Attribute(name=u'object_id', type=u'integer', base=False, multi=False,
            special=AdminTableSpecial(u'server_id')),
        Attribute(name=u'hostname', type=u'string', base=True, multi=False,
            special=AdminTableSpecial(u'hostname')),
        Attribute(name=u'servertype', type=u'string', base=True, multi=False,
            special=AdminTableSpecial(u'servertype_id')),
        Attribute(name=u'intern_ip', type=u'ip', base=True, multi=False,
            special=AdminTableSpecial(u'intern_ip')),
        Attribute(name=u'segment', type=u'string', base=True, multi=False,
            special=AdminTableSpecial(u'segment')),
        Attribute(name=u'all_ips', type=u'ip', base=False, multi=True,
            special=CombinedSpecial(u'intern_ip', u'additional_ips'))
    ]

    # Read all attributes
    lookups.attr_ids = {}
    lookups.attr_names = {}
    for attr in chain(Attribute.objects.all(), special_attributes):
        if attr.name == u'additional_ips':
            attr.type = u'ip'
        # XXX: Dirty hack for old structure
        if attr.name == 'MAC':
            attr.name = 'mac'
        lookups.attr_ids[attr.pk] = attr
        lookups.attr_names[attr.name] = attr
    
    # Read all servertypes
    lookups.stype_ids = {}
    lookups.stype_names = {}
    for stype in ServerType.objects.all():
        lookups.stype_ids[stype.pk] = stype
        lookups.stype_names[stype.name] = stype
    
    # Read all servertype attributes
    # Bypass Django ORM for performance reasons
    lookups.stype_attrs = {}
    c = connection.cursor()
    c.execute(u'SELECT servertype_id, attrib_id, required, attrib_default, '
              u'regex, default_visible FROM servertype_attributes')
    for row in c.fetchall():
        row = list(row)
        try:
            row[4] = re.compile(row[4])
        except (TypeError, re.error):
            row[4] = None
        stype_attr = ServerTypeAttr._make(row)
        stype = lookups.stype_ids[stype_attr.servertype_id]
        if not hasattr(stype, u'attributes'):
            stype.attributes = []
        attribute = lookups.attr_ids[stype_attr.attribute_id]
        stype.attributes.append(attribute)
        index = (stype_attr.servertype_id, stype_attr.attribute_id)
        lookups.stype_attrs[index] = stype_attr
        
        servertype = lookups.stype_ids[stype_attr.servertype_id]
        index = (servertype.name, attribute.name)
        lookups.stype_attrs[index] = stype_attr
    
    # Add attributes from admin_server to servertype attributes
    for servertype in lookups.stype_ids.itervalues():
        special_stype_attr = ServerTypeAttr(servertype.pk, -1, False, None,
                None, True)
        for attr in special_attributes:
            if attr.base:
                index = (servertype.name, attr.name)
                lookups.stype_attrs[index] = special_stype_attr

_read_lookups()
request_started.connect(_read_lookups)
