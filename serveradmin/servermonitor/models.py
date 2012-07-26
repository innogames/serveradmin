import socket

from django.conf import settings

PERIODS = ('hourly', 'daily', 'weekly', 'monthly', 'yearly')

def get_available_graphs(hostname):
    # FIXME: Validate hostname!
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(settings.SERVERMONITOR_SERVER)
    s.sendall('HOSTNAME==serveradmin.admin\n')
    s.sendall('GRAPHS=={0}\nDONE\n'.format(hostname))
    fileobj = s.makefile()
    return fileobj.readline().split()

def get_graph_url(hostname, graph_name):
    return settings.SERVERMONITOR_GRAPH_URL.format(
            hostname=hostname, graph=graph_name)

def reload_graphs(*updates):
    """Reload many graphs. Expects tuples with hostname and graphs.

    Example::
       
       reload_graphs(('techerror.support', ['io2-hourly', 'io2-daily']),
                     ('serveradmin.admin', ['net-hourly']))
    """
    # FIXME: Validate hostname!
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(settings.SERVERMONITOR_SERVER)
    s.sendall('HOSTNAME==serveradmin.admin\n')
    for hostname, graphs in updates:
        for graph in graphs:
            graph_name, period = split_graph_name(graph)
            if not period:
                period = ''
            s.sendall('RELOAD=={graph}##{period}##{hostname}##\n'.format(
                    graph=graph_name, period=period, hostname=hostname))
    s.sendall('DONE\n')
    fileobj = s.makefile()
    return ['SUCCESS' == line.strip() for line in fileobj.readlines()]
    

_period_extensions = tuple('-' + period for period in PERIODS)
def split_graph_name(graph):
    if graph.endswith(_period_extensions):
        graph_name, period = graph.rsplit('-', 1)
        return graph_name, period
    else:
        return graph,  None

def join_graph_name(graph, period):
    return '-'.join((graph, period)) if period else graph
