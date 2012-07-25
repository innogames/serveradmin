import socket

from django.db import models
from django.conf import settings

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
        graph_name, period = split_graph_name(graphs)
        if not period:
            period = ''
        s.sendall('RELOAD=={graph}##{period}##{hostname}\n'.format(
                graph=graph_name, period=period, hostname=hostname))
    s.sendall('DONE')
    fileobj = s.makefile()
    return ['SUCCESS' == line.strip() for line in fileobj.readlines()]
    

def split_graph_name(graph):
    if graph.endswith(('-hourly', '-daily', '-weekly', '-monthly', '-yearly')):
        graph_name, period = graph.rsplit('-', 1)
        return graph_name, period
    else:
        return graph,  None
