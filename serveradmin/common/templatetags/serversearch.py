"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

from json import dumps

from django import template
from django.conf import settings

from adminapi.filters import ExactMatch, filter_classes
from serveradmin.serverdb.models import Attribute, Servertype

register = template.Library()


@register.inclusion_tag('serversearch.html')
def serversearch_js(search_id):
    servertypes = Servertype.objects.all()
    attributes = list(Attribute.objects.all())
    attributes.extend(Attribute.specials.values())

    return {
        'servertypes_json': dumps({s.servertype_id: {} for s in servertypes}),
        'attributes_json': dumps({
            a.attribute_id: {
                'multi': a.multi,
                'type': a.type,
                'regexp': a.regexp,
            }
            for a in attributes
        }),
        'filters_json': dumps(
            [
                f.__name__
                for f in filter_classes
                # TODO Don't check for "Deprecated"
                if f != ExactMatch and not f.__doc__.startswith('Deprecated')
            ]
        ),
        'search_id': search_id,
        'STATIC_URL': settings.STATIC_URL,
    }
