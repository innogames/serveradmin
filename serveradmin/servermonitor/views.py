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
from comments.forms import CommentForm

from adminapi.utils.parse import parse_query
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.serverdb.models import Segment, SegmentUsage, ServerType
from serveradmin.servermonitor.models import (get_available_graphs,
        get_graph_url, split_graph_name, join_graph_name, reload_graphs,
        PERIODS, query_livegraph)
from serveradmin.servermonitor.getinfo import get_information

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
                    'hosts': []
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
    template_info.update(get_information(hostnames, hardware))

    template_info.update({
        'matched_servers': matched_servers,
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
            # Don't show graph with custom timespans
            if period.startswith('custom'):
                continue
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
        server_id = query(hostname=hostname).get().object_id
    except (KeyError, DatasetError):
        return HttpResponseBadRequest('No such server')
    
    return TemplateResponse(request, 'servermonitor/livegraph.html', {
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'hostname': hostname,
        'server_id': server_id
    })

@login_required
def livegraph_data(request):
    try:
        hostname = request.GET['hostname']
        server = query(hostname=hostname).get()
    except (KeyError, DatasetError):
        return HttpResponseBadRequest('No such server')
    
    # Ask dom0 about performance data for the domU
    if 'xen_host' in server and server['xen_host'] != server['hostname']:
        try:
            data = query_livegraph(server['xen_host'], 'guest', server['hostname'])
        except socket.error:
            data = {}
    else:
        data = {}
    
    # ask domU itself for performance data
    try:
        server_data = query_livegraph(server['intern_ip'].as_ip(), 'host')
    except (socket.error, ValueError):
        server_data = {}

    # combine performance data
    data.update(server_data)
    
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

@login_required
def segments_info(request):
    try:
        bins = [int(x) for x in request.GET['bins'].split(',')]
    except (KeyError, ValueError):
        bins = [0, 5, 70]
    bin_list = []
    last = 100
    for start in reversed(bins):
        bin_list.append({'start': start, 'stop': last})
        last = start
    bin_list.reverse()
    
    segments = []
    for segment in Segment.objects.select_related():
        try:
            usage = segment.usage.description
        except SegmentUsage.DoesNotExist:
            usage = 'unknown'

        segments.append({
            'name': segment.segment,
            'info': _get_segment_info(segment, bins),
            'usage': usage
        })

    comment_form = CommentForm(initial={'type': 'segmentinfo'})
    
    return TemplateResponse(request, 'servermonitor/segments_info.html', {
        'segments': segments,
        'bin_list': bin_list,
        'comment_form': comment_form
    })

def _get_segment_info(segment, bins):
    reversed_bins = list(reversed(bins))
    server_hist = [0] * len(bins)
    
    segment_name = segment.segment
    hosts = query(physical_server=True, cancelled=False, segment=segment_name,
                   servertype=filters.Not('hw_loadbalancer')).restrict('hostname')
    hostnames = [host['hostname'] for host in hosts]
    
    info = get_information(hostnames, disabled_features=['vserver'])
    for host in info['hosts']:
        try:
            cpu_value = host['cpu']['daily']
        except KeyError:
            continue
        for i, start in enumerate(reversed_bins):
            if cpu_value >= start:
                server_hist[i] += 1
                break
    server_hist.reverse()
    
    info['num_servers'] = len(hostnames)
    info['server_hist'] = server_hist
    info['cpu_usage'] = info['cpu_aggregate']['daily']['avg'] / 100.0 / 0.7

    return info

_sort_scores = {'hourly': 1, 'daily': 2, 'weekly': 3, 'monthly': 4,
                'yearly': 5, None: 6}
def _sort_key(graph):
    graph_name, period = split_graph_name(graph)
    return (graph_name, _sort_scores.get(period, 0))
