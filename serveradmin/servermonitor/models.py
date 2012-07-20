import socket

from django.db import models
from django.conf import settings

def get_available_graphs(hostname):
    # FIXME: Validate hostname!
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(settings.SERVERMONITOR_SERVER)
    s.sendall('GRAPHS=={0}\nDONE\n'.format(hostname))
    fileobj = s.makefile()
    return fileobj.readline().split()

def get_graph_url(hostname, graph_name):
    return settings.SERVERMONITOR_GRAPH_URL.format(
            hostname=hostname, graph=graph_name)
