import json
from operator import itemgetter

from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

from adminapi.utils.parse import parse_query
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.servermonitor.models import (GraphValue, ServerData,
        get_available_graphs, get_graph_url, split_graph_name, join_graph_name,
        reload_graphs, PERIODS)

@login_required
@ensure_csrf_cookie
def index(request):
    term = request.GET.get('term', '')
    
    hostname_filter = set()
    if term:
        try:
            query_args = parse_query(term, filters.filter_classes)
            for host in query(**query_args).restrict('hostname', 'xen_host'):
                if 'xen_host' in host:
                    hostname_filter.add(host['xen_host'])
                else:
                    # If it's not guest, it might be a server, so we add it
                    hostname_filter.add(host['hostname'])
        except (ValueError, DatasetError), e:
            return TemplateResponse(request, 'servermonitor/index.html', {
                'search_term': term,
                'error': e.message
            })
    
    hw_query_args = {'physical_server': True, 'cancelled': False}
    if hostname_filter:
        hw_query_args['hostname'] = filters.Any(*hostname_filter)

    hardware = {}
    for hw_host in query(**hw_query_args).restrict('hostname', 'servertype'):
        host_data = {
                'hostname': hw_host['hostname'],
                'servertype': hw_host['servertype'],
                'image': '{url}/graph_sprite/{hostname}.png'.format(
                        url=settings.SERVERMONITOR_URL,
                        hostname=hw_host['hostname']),
                'cpu': {},
                'io': {}
        }
        for period in ('hourly', 'daily', 'yesterday'):
            for what in ('io', 'cpu'):
                host_data[what][period] = 0
        hardware[hw_host['hostname']] = host_data
    hostnames = hardware.keys()

    server_data = ServerData.objects.filter(hostname__in=hostnames).only(
            'hostname', 'mem_free_dom0', 'mem_installed_dom0',
            'disk_free_dom0').values()
    graph_values = (GraphValue.objects.filter(hostname__in=hostnames,
            graph_name__in=['cpu_dom0_value_max_95', 'io2_dom0_value_max_95'])
            .values())
    
    # Annotate hardware with data from server data table
    mem_free_sum = 0
    mem_total_sum = 0
    to_bytes = 1024 * 1024
    for host_info in server_data:
        if host_info['mem_installed_dom0']:
            mem_total = host_info['mem_installed_dom0'] * to_bytes
        else:
            mem_total = None
        hardware[host_info['hostname']].update({
            'guests': host_info['running_vserver'].split(),
            'mem_free': host_info['mem_free_dom0']* to_bytes,
            'mem_total': mem_total,
            'disk_free': host_info['disk_free_dom0']* to_bytes
        })
        
        if host_info['mem_free_dom0']:
            mem_free_sum += host_info['mem_free_dom0']
        if host_info['mem_installed_dom0']:
            mem_total_sum += host_info['mem_installed_dom0']
    
    # Annotate hardware with the values for cpu/io
    for graph_value in graph_values:
        if graph_value['graph_name'] == 'cpu_dom0_value_max_95':
            hardware[graph_value['hostname']]['cpu'][graph_value['period']] = \
                    graph_value['value']
        elif graph_value['graph_name'] == 'io2_dom0_value_max_95':
            hardware[graph_value['hostname']]['io'][graph_value['period']] = \
                    graph_value['value']

    hardware = hardware.values()
    hardware.sort(key=itemgetter('hostname'))
    return TemplateResponse(request, 'servermonitor/index.html', {
        'hardware_hosts': hardware,
        'mem_free_sum': mem_free_sum,
        'mem_free_total': mem_total_sum,
        'search_term': term,
        'error': None
    })


@login_required
@ensure_csrf_cookie
def graph_table(request):
    try:
        hostname = request.GET['hostname']
    except KeyError:
        return HttpResponseBadRequest('You have to provide a hostname')

    graphs = get_available_graphs(hostname)
    
    graph_table = {}
    for graph in graphs:
        graph_name, period = split_graph_name(graph)
        if period:
            graph_dict = graph_table.setdefault(graph_name, {})
            graph_dict[period] = get_graph_url(hostname, graph)
            graph_dict['name'] = graph_name
        else:
            graph_table[graph] = {
                'name': graph,
                'general': get_graph_url(hostname, graph)
            }
    graph_table = sorted(graph_table.values(), key=itemgetter('name'))
    return TemplateResponse(request, 'servermonitor/graph_table.html', {
        'hostname': hostname,
        'graph_table': graph_table,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })

@login_required
@ensure_csrf_cookie
def compare(request):
    hostnames = request.GET.getlist('hostname')
    use_graphs = set() # Will contain shown graphs (without period)
    for graph in request.GET.getlist('graph'):
        graph_name, period = split_graph_name(graph)
        use_graphs.add(graph_name)

    graph_hosts = {} # Contains mapping from graph_name to list of hosts
    host_graphs = {} # Available graphs [hostname] -> (graph_name, period)
    for hostname in hostnames:
        host_graphs[hostname] = set([split_graph_name(graph)
                                 for graph in get_available_graphs(hostname)])

    if not use_graphs:
        for graphs in host_graphs.itervalues():
            use_graphs.update([graph[0] for graph in graphs])

    for hostname in hostnames:
        for graph, period in host_graphs[hostname]:
            if graph in use_graphs:
                graph_hosts.setdefault(graph, set()).add(hostname)

    compare_table = []
    for graph_name in use_graphs:
        graph_hostnames = graph_hosts.get(graph_name, set())
        hosts = []
        for hostname in graph_hostnames:
            host = {
                'hostname': hostname
            }
            for period in PERIODS:
                graph = join_graph_name(graph_name, period)
                if (graph_name, period) in host_graphs[hostname]:
                    image = get_graph_url(hostname, graph)
                else:
                    image = None
                host[period] = {'image': image, 'graph': graph}
            hosts.append(host)
        compare_table.append({
                'name': graph_name,
                'hosts': hosts,
        })

    # Sort table by graph and hostnames
    compare_table.sort(key=lambda x: _sort_key(x['name']))
    for graph_row in compare_table:
        graph_row['hosts'].sort(key=itemgetter('hostname'))
    
    return TemplateResponse(request, 'servermonitor/compare.html', {
        'compare_table': compare_table,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })

@login_required
def graph_popup(request):
    try:
        hostname = request.GET['hostname']
        graph = request.GET['graph']
    except KeyError:
        return HttpResponseBadRequest('You have to supply hostname and graph')

    return TemplateResponse(request, 'servermonitor/graph_popup.html', {
        'hostname': hostname,
        'graph': graph,
        'image': get_graph_url(hostname, graph)
    })


@require_POST
@login_required
def reload(request):
    try:
        hostname = request.POST['hostname']
        graph = request.POST['graph']
    except KeyError:
        return HttpResponseBadRequest('No hostname or graph')

    resp = HttpResponse(mimetype='application/x-json')
    json.dump({'result': reload_graphs((hostname, [graph]))}, resp)
    return resp

_sort_scores = {'hourly': 1, 'daily': 2, 'weekly': 3, 'monthly': 4,
                'yearly': 5, None: 6}
def _sort_key(graph):
    graph_name, period = split_graph_name(graph)
    return (graph_name, _sort_scores.get(period, 0))
