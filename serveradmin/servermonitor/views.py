from operator import itemgetter

from django.template.response import TemplateResponse

from serveradmin.servermonitor.models import get_available_graphs, get_graph_url

def graph_table(request, hostname):
    graphs = get_available_graphs(hostname)
    
    graph_table = {}
    for graph in graphs:
        graph_name, period = _split_graph_name(graph)
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
    for hostname in sorted(hostnames):
        available_graphs = get_available_graphs(hostname)
        print available_graphs
        for graph in available_graphs:
            if graph in use_graphs:
                graph_hosts.setdefault(graph, []).append(hostname)

    compare_table = [{'name': graph,
                      'hosts': graph_hosts.get(graph, []),
                      'image': get_graph_url(hostname, graph)
                     } for graph in use_graphs]
    compare_table.sort(key=itemgetter('name'))
    return TemplateResponse(request, 'servermonitor/compare.html', {
        'compare_table': compare_table
    })

def _split_graph_name(graph):
    if graph.endswith(('-hourly', '-daily', '-weekly', '-monthly', '-yearly')):
        graph_name, period = graph.rsplit('-', 1)
        return graph_name, period
    else:
        return graph,  None
