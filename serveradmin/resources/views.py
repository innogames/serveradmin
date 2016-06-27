import collections

from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

import django_urlauth.utils

from adminapi.utils.parse import parse_query
from serveradmin.graphite.models import Collection, NumericCache
from serveradmin.dataset import query, filters
from serveradmin.dataset.base import DatasetError
from serveradmin.serverdb.models import Servertype, Segment

@login_required
@ensure_csrf_cookie
def index(request):
    """The hardware resources page
    """

    term = request.GET.get('term', request.session.get('term', ''))
    current_collection = request.GET.get('current_collection', request.session.get('current_collection', 0))
    current_segment    = request.GET.get('current_segment',    request.session.get('current_segment',   ''))
    current_stype      = request.GET.get('current_stype',      request.session.get('current_stype',     ''))

    try:
        current_collection = int(current_collection)
    except ValueError:
        current_collection = 0

    template_info = {
        'search_term': term,
        'segments': Segment.objects.all(),
        'servertypes': Servertype.objects.all(),
        'collections': Collection.objects.filter(overview=True).order_by('attribute'),
        'current_collection': current_collection,
        'current_segment': current_segment,
        'current_stype': current_stype,
    }

    hostnames = []
    matched_hostnames = []
    if term:
        try:
            query_args = parse_query(term, filters.filter_classes)
            host_query = query(**query_args).restrict('hostname', 'xen_host')
            for host in host_query:
                matched_hostnames.append(host['hostname'])
                if 'xen_host' in host:
                    hostnames.append(host['xen_host'])
                else:
                    # If it's not guest, it might be a server, so we add it
                    hostnames.append(host['hostname'])
            understood = host_query.get_representation().as_code()
            request.session['term'] = term

            if len(hostnames) == 0:
                template_info.update({
                    'understood': understood,
                })
                return TemplateResponse(request, 'resources/index.html',
                        template_info)
        except (ValueError, DatasetError), e:
            template_info.update({
                'error': e.message
            })
            return TemplateResponse(request, 'resources/index.html',
                    template_info)
    else:
        understood = query().get_representation().as_code() # It's lazy :-)

    # If a graph collection was specified, use it.
    if current_collection > 0:
        collection = Collection.objects.filter(id=current_collection)[0]
    else:
    # Otherwise use the 1st one found. Now that is ugly! But it is the one for Dom0s.
        collection = Collection.objects.filter(overview=True)[0]
    print "collection:", collection
    templates = list(collection.template_set.all())
    variations = list(collection.variation_set.all())

    columns = []
    graph_index = 0
    offset = settings.GRAPHITE_SPRITE_WIDTH + settings.GRAPHITE_SPRITE_SPACING
    for template in templates:
        if template.numeric_value:
            columns.append({
                'name': unicode(template),
                'numeric_value': True,
            })
        else:
            for variation in variations:
                columns.append({
                    'name': unicode(template) + ' ' + unicode(variation),
                    'numeric_value': False,
                    'graph_index': graph_index,
                    'sprite_offset': graph_index * offset,
                })
                graph_index += 1

    hosts = collections.OrderedDict()

    # If a graph collection was given, do not limit to physical servers.
    if current_collection > 0:
        query_kwargs = {'cancelled': False}
    else:
        query_kwargs = {'physical_server': True, 'cancelled': False}

    if len(hostnames) > 0:
        query_kwargs['hostname'] = filters.Any(*hostnames)
    for server in query(**query_kwargs).restrict('hostname', 'servertype').order_by('hostname'):
        hosts[server['hostname']] = {
            'hostname': server['hostname'],
            'servertype': server['servertype'],
            'guests': [],
            'columns': list(columns),
        }

    # Add guests for the table cells.
    guests = False
    query_kwargs = {'xen_host': filters.Any(*hosts.keys()), 'cancelled': False}
    for server in query(**query_kwargs).restrict('hostname', 'xen_host').order_by('hostname'):
        guests = True
        hosts[server['xen_host']]['guests'].append(server['hostname'])

    # Add cached numerical values to the table cells.
    for numericCache in NumericCache.objects.filter(hostname__in=hosts.keys()):
        index = [c['name'] for c in columns].index(unicode(numericCache.template))
        column = dict(columns[index])
        column['value'] = numericCache.value
        hosts[numericCache.hostname]['columns'][index] = column

    template_info.update({
        'hosts': hosts.values(),
        'matched_hostnames': matched_hostnames,
        'understood': understood,
        'error': None,
        'guests': guests,
        'GRAPHITE_SPRITE_URL': settings.GRAPHITE_SPRITE_URL,
    })
    return TemplateResponse(request, 'resources/index.html', template_info)

@login_required
def graph_popup(request):
    try:
        hostname = request.GET['hostname']
        graph = request.GET['graph']
    except KeyError:
        return HttpResponseBadRequest('You have to supply hostname and graph')

    # It would be more efficient to filter the collections on the database,
    # but we don't bother because they are unlikely to be more than a few
    # marked as overview.
    for collection in Collection.objects.filter(overview=True):
        servers = collection.query(hostname=hostname)

        if servers:
            table = collection.graph_table(servers.get())
            params = [v2 for k1, v1 in table for k2, v2 in v1][int(graph)]
            token = django_urlauth.utils.new_token(request.user.username,
                                                   settings.GRAPHITE_SECRET)
            url = (settings.GRAPHITE_URL + '/render?' + params + '&' +
                   '__auth_token=' + token)

            return TemplateResponse(request, 'resources/graph_popup.html', {
                'image': url
            })

@login_required
def segments(request):

    counters = {}
    for server in query().restrict(
            'segment',
            'servertype',
            'project',
            'disk_size_gib',
            'memory',
            'num_cpu',
        ):

        if server['segment'] not in counters:
            counters[server['segment']] = [
                    dict(), # For servertypes
                    dict(), # For project
                    0,      # For disk_size_gib
                    0,      # For memory
                    0,      # For num_cpu
                ]

        if server['servertype'] not in counters[server['segment']][0]:
            counters[server['segment']][0][server['servertype']] = 0

        if server['project'] not in counters[server['segment']][1]:
            counters[server['segment']][1][server['project']] = 0

        counters[server['segment']][0][server['servertype']] += 1
        counters[server['segment']][1][server['project']] += 1

        if 'disk_size_gib' in server:
            counters[server['segment']][2] += server['disk_size_gib']

        if 'memory' in server:
            counters[server['segment']][3] += server['memory']

        if 'num_cpu' in server:
            counters[server['segment']][4] += server['num_cpu']

    items = []
    for segment in Segment.objects.all():

        item = {
                'name': segment.segment_id,
                'description': segment.description,
                'servertypes': [],
                'projects': [],
                'disk_size_gib': 0,
                'memory': 0,
                'num_cpu': 0,
            }

        if segment.segment_id in counters:
            item['servertypes'] = counters[segment.segment_id][0].items()
            item['servertypes'].sort()
            item['projects'] = counters[segment.segment_id][1].items()
            item['projects'].sort()
            item['disk_size_gib'] = counters[segment.segment_id][2]
            item['memory'] = counters[segment.segment_id][3]
            item['num_cpu'] = counters[segment.segment_id][4]

        items.append(item)

    return TemplateResponse(request, 'resources/segments.html', {
            'segments': items,
        })
