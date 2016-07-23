import json

from django import template
from django.conf import settings

from serveradmin.dataset import filters
from serveradmin.serverdb.models import Attribute

register = template.Library()


@register.inclusion_tag('serversearch.html')
def serversearch_js(search_id):
    attributes = {
        a.pk: {
            'multi': a.multi,
            'type': a.type,
        }
        for a in Attribute.objects.all()
    }

    filter_dict = {}
    for filt in filters.filter_classes.iterkeys():
        if filt == 'exactmatch':
            continue
        # TODO: Fill with real description
        filt = filt.capitalize()
        filter_dict[filt] = filt

    return {
        'attributes_json': json.dumps(attributes),
        'filters_json': json.dumps(filter_dict),
        'search_id': search_id,
        'STATIC_URL': settings.STATIC_URL
    }
