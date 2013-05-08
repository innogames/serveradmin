import socket
import json
import re
import random

from django.db import models
from django.conf import settings

from serveradmin.common.utils import validate_hostname

PERIODS = ('hourly', 'daily', 'weekly', 'monthly', 'yearly')

class ServermonitorError(Exception):
    pass

class GraphValue(models.Model):
    graph_name = models.CharField(max_length=50, db_column='graphname')
    hostname = models.CharField(max_length=50)
    period = models.CharField(max_length=20, db_column='spanname')
    value = models.FloatField()

    def __unicode__(self):
        return '{0}-{1} on {2}'.format(self.graph_name, self.hostname,
                self.period)

    class Meta:
        db_table = 'graph_value'

class GraphLastUpdate(models.Model):
    graph_name = models.CharField(max_length=50, db_column='graphname')
    hostname = models.CharField(max_length=50)
    period = models.CharField(max_length=20, db_column='spanname')
    last_update = models.DateTimeField(null=True)
    
    def __unicode__(self):
        return '{0}-{1} on {2}'.format(self.graph_name, self.hostname,
                self.period)

    class Meta:
        db_table = 'graph_last_update'

class ServerData(models.Model):
    hostname = models.CharField(max_length=255, primary_key=True)
    disk_free_dom0 = models.IntegerField()
    mem_free_dom0 = models.IntegerField()
    mem_installed_dom0 = models.IntegerField(null=True)
    running_vserver = models.TextField()
    cpu_sum = models.IntegerField()
    updatetime = models.IntegerField()
    cpu_info_dom0 = models.CharField(max_length=255)
    io_hw_dom0 = models.CharField(max_length=255)
    io_hddsum_dom0 = models.CharField(max_length=255)
    xen_hwcaps_dom0 = models.CharField(max_length=255)
    xen_version_dom0 = models.CharField(max_length=255)
    last_update = models.DateTimeField(null=True)
    lun_usage = models.CharField(max_length=255)

    def __unicode__(self):
        return self.hostname

    class Meta:
        db_table = 'serverdata'

class ServermonitorConnection(object):
    def __init__(self):
        self._sock = None
        self._fileobj = None
        self._authed = False
        self._done = False
    
    def connect(self, host=None):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if host is None:
            host = settings.SERVERMONITOR_SERVER
        self._sock.connect(host)
        self._fileobj = self._sock.makefile()
    
    def authenticate(self, hostname=None):
        self._authed = True
        if hostname is None:
            hostname = 'serveradmin.admin'
        self.command('hostname', hostname)
    
    def command(self, command_name, *args):
        if not self._sock:
            self.connect()
        if not self._authed:
            self.authenticate()
        
        args = [arg if isinstance(arg, basestring) else str(arg)
                for arg in args]
        for arg in args:
            if '##' in arg or '\n' in arg:
                raise ValueError('Invalid arg: ' + repr(arg))
        
        if not args:
            command = command_name.upper() + '\n'
        else:
            command = '{0}=={1}\n'.format(command_name.upper(), '##'.join(args))
        print command,
        self._sock.sendall(command)

    def done(self):
        self._done = True
        self.command('done')

    def check_success(self):
        return ['SUCCESS' == line.strip() for line in self.get_response('lines')]

    def get_response(self, mode='lines'):
        if not self._done:
            self.done()

        if mode == 'line':
            line = self._fileobj.readline()
            if line.startswith('ERR'):
                raise ServermonitorError(line.split(None, 1)[1])
            return line
        elif mode == 'lines':
            return self._fileobj.readlines()
        else:
            return self._fileobj.read()

        return self._fileobj.readlines()


def get_available_graphs(hostname):
    if not validate_hostname:
        raise ValueError('Invalid hostname ' + hostname)
    conn = ServermonitorConnection()
    conn.command('graphs', hostname)
    return conn.get_response('line').split()

def get_graph_url(hostname, graph):
    return '{url}/graph/{hostname}/{graph}.png'.format(
            url=settings.SERVERMONITOR_URL,
            hostname=hostname,
            graph=graph)

def reload_graphs(*updates):
    """Reload many graphs. Expects tuples with hostname and graphs.

    Example::
       
       reload_graphs(('techerror.support', ['io2-hourly', 'io2-daily']),
                     ('serveradmin.admin', ['net-hourly']))
    """
    for host, _graphs in updates:
        if not validate_hostname(host):
            raise ValueError('Invalid hostname ' + host)

    conn = ServermonitorConnection()
    for hostname, graphs in updates:
        for graph in graphs:
            graph_name, period = split_graph_name(graph)
            if not period:
                period = ''
        # Reload takes an unused argument for backward compatibility
        conn.command('reload', graph_name, period, hostname, '')
    print conn.get_response('lines')
    return conn.check_success()

def draw_custom_graph(graph_name, hostname, start, end):
    if not validate_hostname(hostname):
        raise ValueError('Invalid hostname ' + hostname)
    name = 'custom{0}'.format(random.randint(0, 99999))
    conn = ServermonitorConnection()
    conn.command('draw', graph_name, name, start, end, hostname)
    if all(conn.check_success()):
        return get_graph_url(hostname, join_graph_name(graph_name, name))
    else:
        raise ServermonitorError('Could not draw graph')

def get_rrd_data(create_def, hostname, df='AVERAGE', start=None, end=None,
                 aggregate=None):
    conn = ServermonitorConnection()
    conn.command('getdata', create_def, hostname, df, start, end, aggregate)
    return json.loads(conn.get_response('line'))

_period_extensions = tuple('-' + period for period in PERIODS)
_period_custom_re = re.compile('custom\d+$')
def split_graph_name(graph):
    if graph.endswith(_period_extensions) or _period_custom_re.search(graph):
        graph_name, period = graph.rsplit('-', 1)
        return graph_name, period
    else:
        return graph,  None

def join_graph_name(graph, period):
    return '-'.join((graph, period)) if period else graph

def query_livegraph(server, info_type='host', hostname=''):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 8462))
    s.sendall('{0} livegraph-data {1} {2}\n'.format(server, info_type, hostname))
    fileobj = s.makefile()
    message = fileobj.readline()
    s.close()
    data = dict(zip(*[iter(message.split())]*2))
    for key, value in data.items():
       try:
           data[key] = float(value)
       except ValueError:
           data[key] = float('nan')
    
    return data
