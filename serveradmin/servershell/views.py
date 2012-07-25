try:
    import simplejson as json
except ImportError:
    import json

from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie

from adminapi.utils.json import json_encode_extra
from adminapi.utils.parse import parse_query
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.dataset.filters import filter_classes
from serveradmin.dataset.base import lookups

@login_required
@ensure_csrf_cookie
def index(request):
    return TemplateResponse(request, 'servershell/index.html', {
        'attribute_list': sorted(lookups.attr_names.keys()),
    })

@login_required
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

@login_required
def get_results(request):
    term = request.GET.get('term', '')
    try:
        offset = int(request.GET.get('offset', '0'))
        limit = min(int(request.GET.get('limit', '0')), 250)
    except ValueError:
        offset = 0
        limit = 25

    order_by = request.GET.get('order_by')
    order_dir = request.GET.get('order_dir', 'asc')
    
    shown_attributes = ['hostname', 'intern_ip', 'servertype']
    try:
        query_args = parse_query(term, filter_classes)
        
        # Add attributes with non-constant values to the shown attributes
        for attr, value in query_args.iteritems():
            if not isinstance(value, (filters.ExactMatch, basestring)):
                # FIXME: Just a dirty workaround
                if attr == 'all_ips':
                    if u'intern_ip' not in shown_attributes:
                        shown_attributes.append(u'additional_ips')
                    if u'additional_ips' not in shown_attributes:
                        shown_attributes.append(u'additional_ips')
                    continue
                if attr not in shown_attributes:
                    shown_attributes.append(attr)
        
        q = query(**query_args).limit(offset, limit)
        if order_by:
            q = q.order_by(order_by, order_dir)
        results = q.get_raw_results()
        num_servers = q.get_num_rows()
    except (ValueError, DatasetError), e:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': e.message
        }))

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': q.get_representation().as_code(hide_extra=True),
        'servers': results,
        'num_servers': num_servers,
        'shown_attributes': shown_attributes,
    }, default=json_encode_extra), mimetype='application/x-json')

def export(request):
    term = request.GET.get('term', '')
    try:
        query_args = parse_query(term, filter_classes)
        q = query(**query_args).restrict('hostname')
    except (ValueError, DatasetError), e:
        return HttpResponse(e.message, status=400)

    hostnames = u' '.join(server['hostname'] for server in q)
    return HttpResponse(hostnames, mimetype='text/plain')
