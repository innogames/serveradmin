import json
from operator import itemgetter

from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from serveradmin.servermonitor.models import (get_available_graphs, get_graph_url,
        split_graph_name, join_graph_name, reload_graphs, PERIODS)

def graph_table(request, hostname):
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
                graph_hosts.setdefault(graph, []).append(hostname)

    compare_table = []
    for graph_name in use_graphs:
        graph_hostnames = graph_hosts.get(graph_name, [])
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

@require_POST
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
