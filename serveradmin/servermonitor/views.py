from __future__ import division

import json
import math
import socket
import time
from operator import itemgetter
from itertools import izip_longest

from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

import nrpe
from adminapi.utils.parse import parse_query
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.dataset.models import Segment, ServerType
from serveradmin.servermonitor.models import (GraphValue, ServerData,
        get_available_graphs, get_graph_url, split_graph_name, join_graph_name,
        reload_graphs, PERIODS)

@login_required
@ensure_csrf_cookie
def index(request):
    term = request.GET.get('term', request.session.get('term', ''))
    
    template_info = {
        'search_term': term,
        'segments': Segment.objects.order_by('segment'),
        'servertypes': ServerType.objects.order_by('name')
    }
    
    hostname_filter = set()
    matched_servers = set()
    if term:
        try:
            query_args = parse_query(term, filters.filter_classes)
            host_query = query(**query_args).restrict('hostname', 'xen_host')
            for host in host_query:
                matched_servers.add(host['hostname'])
                if 'xen_host' in host:
                    hostname_filter.add(host['xen_host'])
                else:
                    # If it's not guest, it might be a server, so we add it
                    hostname_filter.add(host['hostname'])
            understood = host_query.get_representation().as_code()
            request.session['term'] = term

            if not matched_servers:
                template_info.update({
                    'understood': host_query.get_representation().as_code(),
                    'hardware_hosts': []
                })
                return TemplateResponse(request, 'servermonitor/index.html',
                        template_info)
        except (ValueError, DatasetError), e:
            template_info.update({
                'error': e.message
            })
            return TemplateResponse(request, 'servermonitor/index.html',
                    template_info)
    else:
        understood = query().get_representation().as_code() # It's lazy :-)
    
    hw_query_args = {'physical_server': True, 'cancelled': False}
    if hostname_filter:
        hw_query_args['hostname'] = filters.Any(*hostname_filter)


    periods = ('hourly', 'daily', 'yesterday')
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
        for period in periods:
            for what in ('io', 'cpu'):
                host_data[what][period] = None
        hardware[hw_host['hostname']] = host_data
    hostnames = hardware.keys()

    server_data = ServerData.objects.filter(hostname__in=hostnames).only(
            'hostname', 'mem_free_dom0', 'mem_installed_dom0',
            'disk_free_dom0', 'running_vserver').values()
    graph_values = (GraphValue.objects.filter(hostname__in=hostnames,
            graph_name__in=['cpu_dom0_value_max_95', 'io2_dom0_value_max_95'])
            .values())
    
    # Annotate hardware with data from server data table
    mem_free_sum = 0
    mem_free_count = 0
    mem_total_sum = 0
    mem_total_count = 0
    disk_free_sum = 0
    disk_free_count = 0
    
    cpu_aggregate = {}
    io_aggregate = {}
    for period in periods:
        cpu_aggregate[period] = {'sum': 0, 'count': 0}
        io_aggregate[period] = {'sum': 0, 'count': 0}
    
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
            mem_free_count += 1
        if host_info['mem_installed_dom0']:
            mem_total_sum += host_info['mem_installed_dom0']
            mem_total_count += 1
        if host_info['disk_free_dom0']:
            disk_free_sum += host_info['disk_free_dom0']
            disk_free_count += 1
    
    # Annotate hardware with the values for cpu/io
    for graph_value in graph_values:
        if graph_value['graph_name'] == 'cpu_dom0_value_max_95':
            hardware[graph_value['hostname']]['cpu'][graph_value['period']] = \
                    int(round(graph_value['value']))
            cpu_aggregate[graph_value['period']]['sum'] += graph_value['value']
            cpu_aggregate[graph_value['period']]['count'] += 1
        elif graph_value['graph_name'] == 'io2_dom0_value_max_95':
            hardware[graph_value['hostname']]['io'][graph_value['period']] = \
                    int(round(graph_value['value']))
            io_aggregate[graph_value['period']]['sum'] += graph_value['value']
            io_aggregate[graph_value['period']]['count'] += 1

    hardware = hardware.values()
    hardware.sort(key=itemgetter('hostname'))

    mem_free_sum *= to_bytes
    mem_total_sum *= to_bytes
    disk_free_sum *= to_bytes
    
    for period in periods:
        cpu_count = cpu_aggregate[period]['count']
        cpu_count = cpu_count if cpu_count else 1
        cpu_aggregate[period]['avg'] = round(cpu_aggregate[period]['sum'] /
                cpu_count, 2)

        io_count = io_aggregate[period]['count']
        io_count = io_count if io_count else 1
        io_aggregate[period]['avg'] = round(cpu_aggregate[period]['sum'] /
                io_count, 2)
    
    mem_free_count = mem_free_count if mem_free_count else 1
    mem_total_count = mem_total_count if mem_total_count else 1
    disk_free_count = disk_free_count if disk_free_count else 1
    template_info.update({
        'hardware_hosts': hardware,
        'matched_servers': matched_servers,
        'mem_free_sum': mem_free_sum,
        'mem_free_avg': mem_free_sum / mem_free_count,
        'mem_total_sum': mem_total_sum,
        'mem_total_avg': mem_total_sum / mem_total_count,
        'disk_free_sum': disk_free_sum,
        'disk_free_avg': disk_free_sum / disk_free_count,
        'cpu_aggregate': cpu_aggregate,
        'io_aggregate': io_aggregate,
        'understood': understood,
        'error': None
    })
    return TemplateResponse(request, 'servermonitor/index.html', template_info)


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
            graph_dict['name'] = graph_name
            graph_dict[period] = {
                'image': get_graph_url(hostname, graph),
                'graph': graph
            }
        else:
            graph_table[graph] = {
                'name': graph,
                'general': {
                    'image': get_graph_url(hostname, graph),
                    'graph': graph
                }
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
    periods = set(request.GET.getlist('period'))
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
                'hostname': hostname,
                'images': []
            }
            for period in PERIODS:
                if periods and period not in periods:
                    continue
                graph = join_graph_name(graph_name, period)
                if (graph_name, period) in host_graphs[hostname]:
                    image = get_graph_url(hostname, graph)
                else:
                    image = None
                host['images'].append({'period': period,
                                       'image': image,
                                       'graph': graph})

            # Pop non existing images at the end
            for graph_entry in reversed(host['images']):
                if graph_entry['image'] is None:
                    host['images'].pop()
                else:
                    break
            host['num_rows'] = int(math.ceil(len(host['images']) / 3))
            host['images'] = izip_longest(*[iter(host['images'])] * 3)
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

@login_required
def livegraph(request):
    try:
        hostname = request.GET['hostname']
    except KeyError:
        return HttpResponseBadRequest('You have to supply hostname')
    
    return TemplateResponse(request, 'servermonitor/livegraph.html', {
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'hostname': hostname
    })

@login_required
def livegraph_data(request):
    try:
        hostname = request.GET['hostname']
        intern_ip = query(hostname=hostname).get()['intern_ip'].as_ip()
    except (KeyError, DatasetError):
        return HttpResponseBadRequest('No such server')

    try:
        code, message = nrpe.send_query('check_livegraph', intern_ip,
                timeout=0.5)
        data = dict(zip(*[iter(message.split())]*2))
        for key, value in data.items():
            try:
                data[key] = float(value)
            except ValueError:
                data[key] = float('nan')
    except (socket.error, ValueError, nrpe.InvalidResponse):
        data = {}
    
    return HttpResponse(json.dumps({
        'time': int(time.time() * 1000),
        'data': data
    }), mimetype='application/x-json')


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
