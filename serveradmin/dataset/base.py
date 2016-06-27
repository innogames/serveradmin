import re
import uuid
from threading import local
from itertools import chain
from collections import namedtuple

from django.db import connection
from django.core.cache import cache
from django.core.signals import request_started

from serveradmin.serverdb.models import Attribute, Servertype, Segment, Project

lookups = local()
ServertypeAttr = namedtuple('ServertypeAttr', (
        'servertype_id',
        'attribute_id',
        'required',
        'default',
        'regexp',
        'visible',
    ))


# The base exception.  Ideally, the callers should not except it, but
# finer-grained exceptions inherited from it.
class DatasetError(Exception):
    pass


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
                    attrib_id=u'object_id',
                    type=u'integer',
                    base=False,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'server_id'),
                ),
            Attribute(
                    attrib_id=u'hostname',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'hostname', unique=True),
                ),
            Attribute(
                    attrib_id=u'servertype',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'servertype_id'),
                ),
            Attribute(
                    attrib_id=u'project',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'project_id'),
                ),
            Attribute(
                    attrib_id=u'intern_ip',
                    type=u'ip',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'intern_ip'),
                ),
            Attribute(
                    attrib_id=u'segment',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'segment_id'),
                ),
        ]
    lookups.special_attributes = special_attributes

    # Read all attributes
    lookups.attributes = {}
    for attribute in chain(Attribute.objects.all(), special_attributes):
        lookups.attributes[attribute.pk] = attribute

    # Read all servertypes
    lookups.servertypes = {}
    for servertype in Servertype.objects.all():
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
            attribute = lookups.attributes[row[1]]
            if attribute.type == 'string':
                try:
                    row[4] = re.compile(row[4])
                except (TypeError, re.error):
                    row[4] = None
            else:
                row[4] = None
            row[2] = bool(row[2])
            stype_attr = ServertypeAttr._make(row)
            stype = lookups.servertypes[stype_attr.servertype_id]
            stype.attributes.append(attribute)
            index = (stype_attr.servertype_id, stype_attr.attribute_id)
            lookups.stype_attrs[index] = stype_attr

    # Add attributes from admin_server to servertype attributes
    for servertype in lookups.servertypes.itervalues():
        special_stype_attr = ServertypeAttr(
                servertype.pk,
                -1,
                True,
                None,
                None,
                True,
            )

        for attr in special_attributes:
            if attr.base:
                index = (servertype.pk, attr.pk)
                lookups.stype_attrs[index] = special_stype_attr

_read_lookups()
request_started.connect(_read_lookups)
