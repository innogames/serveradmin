import json
import re

from django.http import HttpResponse
from django.template.response import TemplateResponse

from serveradmin.dataset.base import lookups
from serveradmin.dataset import query, filters, DatasetError

def index(request):
    attributes = {}
    for attr in lookups.attr_ids.itervalues():
        attributes[attr.name] = {
            'multi': attr.multi,
            'type': attr.type
        }
    return TemplateResponse(request, 'servershell/index.html', {
        'attributes': json.dumps(attributes) 
    })

def autocomplete(request):
    autocomplete_list = []
    if 'hostname' in request.GET:
        hostname = request.GET['hostname']
        hostname_regexp = u'^' + re.escape(hostname) + u'.*$'
        try:
            hosts = query(hostname=filters.Regexp(hostname_regexp)).limit(10)
            autocomplete_list += (host['hostname'] for host in hosts)
        except DatasetError:
            pass # If there is no valid query, just don't autocomplete

    if 'attr' in request.GET:
        attr_name = request.GET['attr_name']
        # FIXME: Find distinct values for autocomplete

    return HttpResponse(json.dumps({'autocomplete': autocomplete_list}),
            mimetype='application/x-json')

