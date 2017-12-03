import json

from django import template
from django.conf import settings

from adminapi.filters import ExactMatch, filter_classes
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

    return {
        'attributes_json': json.dumps(attributes),
        'filters_json': json.dumps(
            [
                f.__name__
                for f in filter_classes
                # TODO Don't check for "Deprecated"
                if f != ExactMatch and not f.__doc__.startswith('Deprecated')
            ]
        ),
        'search_id': search_id,
        'STATIC_URL': settings.STATIC_URL
    }
