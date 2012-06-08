import uuid
from threading import local
from itertools import chain

from django.core.cache import cache
from django.core.signals import request_started
from django.db import connection

from serveradmin.dataset.models import Attribute, ServerType

lookups = local()

def _read_lookups(sender=None, **kwargs):
    version = cache.get('dataset_lookups_version')
    if not version:
        version = uuid.uuid1().hex
        cache.add('dataset_lookups_version', version)

    if hasattr(lookups, 'version') and lookups.version == version:
        return
    else:
        lookups.version = version

    special_attributes = [
        Attribute(name='object_id', type='integer', base=True, multi=False),
        Attribute(name='hostname', type='string', base=True, multi=False),
        Attribute(name='servertype', type='string', base=True, multi=False),
        Attribute(name='intern_ip', type='ip', base=True, multi=False),
        Attribute(name='segment', type='string', base=True, multi=False),
        Attribute(name='all_ips', type='ip', base=True, multi=True)
    ]
    lookups.attr_ids = {}
    lookups.attr_names = {}
    for attr in chain(Attribute.objects.all(), special_attributes):
        if attr.name == 'additional_ips':
            attr.type = 'ip'
        lookups.attr_ids[attr.pk] = attr
        lookups.attr_names[attr.name] = attr

    lookups.stype_ids = {}
    lookups.stype_names = {}
    for stype in ServerType.objects.all():
        lookups.stype_ids[stype.pk] = stype
        lookups.stype_names[stype.name] = stype
    
    # Bypass Django ORM for performance reasons
    c = connection.cursor()
    c.execute('SELECT servertype_id, attrib_id FROM servertype_attributes')
    for servertype_id, attr_id in c.fetchall():
        stype = lookups.stype_ids[servertype_id]
        if not hasattr(stype, 'attributes'):
            stype.attributes = []
        stype.attributes.append(lookups.attr_ids[attr_id])

_read_lookups()
request_started.connect(_read_lookups)
