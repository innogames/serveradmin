import json

from django import template

from serveradmin.dataset.base import lookups
from serveradmin.dataset import filters

register = template.Library()

@register.inclusion_tag('serversearch.html')
def serversearch_js():
    attributes = {}
    for attr in lookups.attr_names.itervalues():
        attributes[attr.name] = {
            'multi': attr.multi,
            'type': attr.type
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
    }
