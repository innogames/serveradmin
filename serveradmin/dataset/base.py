import uuid
from threading import local
from itertools import chain

from django.core.cache import cache
from django.core.signals import request_started

from serveradmin.serverdb.models import Attribute, Servertype, Segment, Project

lookups = local()


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

    # Special attributes that don't have an entry in the attribute table
    lookups.special_attributes = [
            Attribute(
                    attribute_id=u'object_id',
                    type=u'integer',
                    base=False,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'server_id'),
                ),
            Attribute(
                    attribute_id=u'hostname',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'hostname', unique=True),
                ),
            Attribute(
                    attribute_id=u'servertype',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'servertype_id'),
                ),
            Attribute(
                    attribute_id=u'project',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'project_id'),
                ),
            Attribute(
                    attribute_id=u'intern_ip',
                    type=u'ip',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'intern_ip'),
                ),
            Attribute(
                    attribute_id=u'segment',
                    type=u'string',
                    base=True,
                    multi=False,
                    group='base',
                    special=ServerTableSpecial(u'segment_id'),
                ),
        ]

    lookups.projects = dict((p.pk, p) for p in Project.objects.all())
    lookups.segments = dict((s.pk, s) for s in Segment.objects.all())
    lookups.servertypes = dict((s.pk, s) for s in Servertype.objects.all())
    lookups.attributes = dict(
        (a.pk, a) for a in chain(
            Attribute.objects.all(), lookups.special_attributes
        )
    )

_read_lookups()
request_started.connect(_read_lookups)
