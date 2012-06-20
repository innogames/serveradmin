import json

from django.http import HttpResponse
from django.template.response import TemplateResponse

from serveradmin.dataset.base import lookups
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.servershell.utils import parse_function_string

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
        try:
            hosts = query(hostname=filters.Startswith(hostname)).limit(10)
            autocomplete_list += (host['hostname'] for host in hosts)
        except DatasetError:
            pass # If there is no valid query, just don't autocomplete

    return HttpResponse(json.dumps({'autocomplete': autocomplete_list}),
            mimetype='application/x-json')

def get_results(request):
    term = request.GET.get('term', '')
    parsed_args = parse_function_string(term, strict=False)

    return HttpResponse(repr(parsed_args))
