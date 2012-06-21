try:
    import simplejson as json
except ImportError:
    import json

from django.http import HttpResponse
from django.template.response import TemplateResponse

from adminapi.utils.json import json_encode_extra
from serveradmin.dataset.base import lookups
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.servershell.utils import parse_function_string, build_query_args

def index(request):
    attributes = {}
    for attr in lookups.attr_names.itervalues():
        attributes[attr.name] = {
            'multi': attr.multi,
            'type': attr.type
        }
    return TemplateResponse(request, 'servershell/index.html', {
        'attributes_json': json.dumps(attributes),
        'attribute_list': sorted(lookups.attr_names.keys())
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
    try:
        offset = int(request.GET.get('offset', '0'))
        limit = min(int(request.GET.get('limit', '0')), 250)
    except ValueError:
        raise
        offset = 0
        limit = 25

    try:
        parsed_args = parse_function_string(term, strict=True)
        query_args = build_query_args(parsed_args)
        q = query(**query_args).limit(offset, limit)
        results = q.get_raw_results()
    except (ValueError, DatasetError), e:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': e.message
        }))

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': q.get_representation().as_string(hide_extra=True),
        'servers': results
    }, default=json_encode_extra))#, mimetype='application/x-json')
