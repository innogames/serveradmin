try:
    import simplejson as json
except ImportError:
    import json

from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.csrf import ensure_csrf_cookie

from adminapi.utils.json import json_encode_extra
from adminapi.utils.parse import parse_query
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.dataset.filters import filter_classes
from serveradmin.dataset.base import lookups
from serveradmin.dataset.commit import commit_changes

@login_required
@ensure_csrf_cookie
def index(request):
    return TemplateResponse(request, 'servershell/index.html', {
        'attribute_list': sorted(lookups.attr_names.keys()),
        'search_term': request.GET.get('term', '')
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

@login_required
def export(request):
    term = request.GET.get('term', '')
    try:
        query_args = parse_query(term, filter_classes)
        q = query(**query_args).restrict('hostname')
    except (ValueError, DatasetError), e:
        return HttpResponse(e.message, status=400)

    hostnames = u' '.join(server['hostname'] for server in q)
    return HttpResponse(hostnames, mimetype='text/plain')

def list_and_edit(request):
    try:
        object_id = request.GET['object_id']
        server = query(object_id=object_id).get()
    except (KeyError, DatasetError):
        raise Http404

    mode = 'edit' if 'edit' in request.GET else 'list'

    non_editable = ['servertype']
    fields = []
    for key, value in server.iteritems():
        fields.append({
            'key': key,
            'value': value,
            'editable': key not in non_editable,
            'type': lookups.attr_names[key].type,
            'multi': lookups.attr_names[key].multi
        })
    
    # Sort keys by some order and then lexographically
    _key_order = ['hostname', 'servertype', 'intern_ip']
    _key_order_lookup = dict((key, i) for i, key in enumerate(_key_order))
    def _sort_key(x):
        return (_key_order_lookup.get(x['key'], 100), x['key'])
    fields.sort(key=_sort_key)

    return TemplateResponse(request, 'servershell/{0}.html'.format(mode), {
        'object_id': server.object_id,
        'fields': fields,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })

@login_required
@permission_required('dataset.change_serverobject')
def commit(request):
    try:
        commit = json.loads(request.POST['commit'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    if 'changes' in commit:
        changes = {}
        for key, value in commit['changes'].iteritems():
            if not key.isdigit():
                continue
            changes[int(key)] = value
        commit['changes'] = changes

    try:
        commit_changes(commit)
    except (ValueError, DatasetError):
        raise

    return HttpResponse('OK')
