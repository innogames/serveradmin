from operator import itemgetter

from django.template.response import TemplateResponse

from serveradmin.servermonitor.models import (get_available_graphs, get_graph_url,
                                           split_graph_name)

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
        'graph_table': graph_table
    })

def compare(request):
    hostnames = request.GET.getlist('hostname')
    use_graphs = set(request.GET.getlist('graph'))
    graph_hosts = {}
    host_graphs = {}
    for hostname in hostnames:
        host_graphs[hostname] = get_available_graphs(hostname)

    if not use_graphs:
        for graphs in host_graphs.itervalues():
            use_graphs.update(graphs)

    for hostname in hostnames:
        for graph in host_graphs[hostname]:
            if graph in use_graphs:
                graph_hosts.setdefault(graph, []).append(hostname)

    compare_table = []
    for graph in use_graphs:
        graph_hostnames = graph_hosts.get(graph, [])
        hosts = [{'hostname': hostname,
                  'image': get_graph_url(hostname, graph)}
                 for hostname in graph_hostnames]
        compare_table.append({
                'name': graph,
                'hosts': hosts,
        })

    # Sort table by graph and hostnames
    compare_table.sort(key=lambda x: _sort_key(x['name']))
    for graph_row in compare_table:
        graph_row['hosts'].sort(key=itemgetter('hostname'))
    
    return TemplateResponse(request, 'servermonitor/compare.html', {
        'compare_table': compare_table
    })

_sort_scores = {'hourly': 1, 'daily': 2, 'weekly': 3, 'monthly': 4,
                'yearly': 5, None: 6}
def _sort_key(graph):
    graph_name, period = split_graph_name(graph)
    return (graph_name, _sort_scores.get(period, 0))
