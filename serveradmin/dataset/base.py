import re
import uuid
from threading import local
from itertools import chain
from collections import namedtuple

from django.db import connection
from django.core.cache import cache
from django.core.signals import request_started

from serveradmin.serverdb.models import Attribute, ServerType, Segment, Project

lookups = local()
ServerTypeAttr = namedtuple('ServerTypeAttr', (
        'servertype_id',
        'attribute_id',
        'required',
        'default',
        'regexp',
        'visible',
    ))

class ServerTableSpecial(object):
    def __init__(self, field, unique=False):
        self.field = field
        self.unique = unique

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
            Attribute(
                    name=u'object_id',
                    type=u'integer',
                    base=False,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'server_id'),
                ),
            Attribute(
                    name=u'hostname',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'hostname', unique=True),
                ),
            Attribute(
                    name=u'servertype',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'servertype_id'),
                ),
            Attribute(
                    name=u'project',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'project_id'),
                ),
            Attribute(
                    name=u'intern_ip',
                    type=u'ip',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'intern_ip'),
                ),
            Attribute(
                    name=u'segment',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'segment_id'),
                ),
        ]
    lookups.special_attributes = special_attributes

    # Read all attributes
    lookups.attr_ids = {}
    lookups.attr_names = {}
    for attr in chain(Attribute.objects.all(), special_attributes):
        lookups.attr_ids[attr.pk] = attr
        lookups.attr_names[attr.name] = attr

    # Read all servertypes
    lookups.servertypes = {}
    for servertype in ServerType.objects.all():
        servertype.attributes = []
        lookups.servertypes[servertype.pk] = servertype

    # Read all segments
    lookups.segments = dict((s.pk, s) for s in Segment.objects.all())

    # Read all projects
    lookups.projects = dict((p.pk, p) for p in Project.objects.all())

    # Read all servertype attributes
    # Bypass Django ORM for performance reasons
    lookups.stype_attrs = {}
    with connection.cursor() as cursor:
        cursor.execute(
                u'SELECT servertype_id, attrib_id, required, attrib_default, '
                u'regex, default_visible FROM servertype_attributes'
            )

        for row in cursor.fetchall():
            row = list(row)
            attribute = lookups.attr_ids[row[1]]
            if attribute.type == 'string':
                try:
                    row[4] = re.compile(row[4])
                except (TypeError, re.error):
                    row[4] = None
            else:
                row[4] = None
            row[2] = bool(row[2])
            stype_attr = ServerTypeAttr._make(row)
            stype = lookups.servertypes[stype_attr.servertype_id]
            stype.attributes.append(attribute)
            index = (stype_attr.servertype_id, stype_attr.attribute_id)
            lookups.stype_attrs[index] = stype_attr

            servertype = lookups.servertypes[stype_attr.servertype_id]
            index = (servertype.pk, attribute.name)
            lookups.stype_attrs[index] = stype_attr

    # Add attributes from admin_server to servertype attributes
    for servertype in lookups.servertypes.itervalues():
        special_stype_attr = ServerTypeAttr(
                servertype.pk,
                -1,
                True,
                None,
                None,
                True,
            )

        for attr in special_attributes:
            if attr.base:
                index = (servertype.pk, attr.name)
                lookups.stype_attrs[index] = special_stype_attr

_read_lookups()
request_started.connect(_read_lookups)
