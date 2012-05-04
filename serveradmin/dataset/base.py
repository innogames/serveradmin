from threading import local

from django.core.signals import request_started

from serveradmin.dataset.models import Attribute, ServerType

lookups = local()
def _read_lookups(sender=None, **kwargs):
    lookups.attr_ids = {}
    lookups.attr_names = {}
    for attr in Attribute.objects.all():
        if attr.name == 'additional_ips':
            attr.type = 'ip'
        lookups.attr_ids[attr.pk] = attr
        lookups.attr_names[attr.name] = attr
    lookups.stype_ids = {}
    lookups.stype_names = {}
    for stype in ServerType.objects.all():
        lookups.stype_ids[stype.pk] = stype
        lookups.stype_names[stype.name] = stype

_read_lookups()
request_started.connect(_read_lookups)
