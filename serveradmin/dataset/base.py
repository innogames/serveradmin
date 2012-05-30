from threading import local
from itertools import chain

from django.core.signals import request_started

from serveradmin.dataset.models import (Attribute, ServerType,
        ServerTypeAttributes)

lookups = local()
def _read_lookups(sender=None, **kwargs):
    special_attributes = [
        Attribute(name='object_id', type='integer', base=True, multi=False),
        Attribute(name='hostname', type='string', base=True, multi=False),
        Attribute(name='servertype', type='string', base=True, multi=False),
        Attribute(name='intern_ip', type='ip', base=True, multi=False)
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
    
    for stype_attr in ServerTypeAttributes.objects.all():
        stype = lookups.stype_ids[stype_attr.servertype_id]
        if not hasattr(stype, 'attributes'):
            stype.attributes = []
        stype.attributes.append(lookups.attr_ids[stype_attr.attrib.pk])

_read_lookups()
request_started.connect(_read_lookups)
