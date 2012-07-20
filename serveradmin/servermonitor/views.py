from operator import itemgetter

from django.template.response import TemplateResponse

from serveradmin.servermonitor.models import get_available_graphs, get_graph_url

def graph_table(request, hostname):
    graphs = get_available_graphs(hostname)
    
    graph_table = {}
    for graph in graphs:
        if graph.endswith(('-hourly', '-daily', '-weekly', '-monthly')):
            graph_name, period = graph.rsplit('-', 1)
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
