from collections import OrderedDict, defaultdict

from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

from adminapi.base import QueryError
from adminapi.parse import parse_query
from serveradmin.graphite.models import (
    GRAPHITE_ATTRIBUTE_ID,
    Collection,
    NumericCache,
)
from serveradmin.dataset import query, filters
from serveradmin.serverdb.models import Project


@login_required     # NOQA: C901
@ensure_csrf_cookie
def index(request):
    """The hardware resources page"""
    term = request.GET.get('term', request.session.get('term', ''))
    collections = list(Collection.objects.filter(overview=True))

    # If a graph collection was specified, use it.  Otherwise use the first
    # one.
    for collection in collections:
        if request.GET.get('current_collection'):
            if str(collection.id) != request.GET['current_collection']:
                continue
        current_collection = collection
        break
    else:
        raise HttpResponseBadRequest('No matching current collection')

    template_info = {
        'search_term': term,
        'collections': collections,
        'current_collection': current_collection.id,
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
            understood = repr(host_query)
            request.session['term'] = term

            if len(hostnames) == 0:
                template_info.update({
                    'understood': understood,
                })
                return TemplateResponse(
                    request, 'resources/index.html', template_info
                )
        except (QueryError, ValidationError) as error:
            template_info.update({
                'error': str(error)
            })
            return TemplateResponse(
                request, 'resources/index.html', template_info
            )
    else:
        understood = repr(query())

    templates = list(current_collection.template_set.all())
    variations = list(current_collection.variation_set.all())
    columns = []
    graph_index = 0
    sprite_width = settings.GRAPHITE_SPRITE_WIDTH
    for template in templates:
        if template.numeric_value:
            columns.append({
                'name': str(template),
                'numeric_value': True,
            })
        else:
            for variation in variations:
                columns.append({
                    'name': str(template) + ' ' + str(variation),
                    'numeric_value': False,
                    'graph_index': graph_index,
                    'sprite_offset': graph_index * sprite_width,
                })
                graph_index += 1

    hosts = OrderedDict()
    query_kwargs = {GRAPHITE_ATTRIBUTE_ID: collection.name}
    if len(hostnames) > 0:
        query_kwargs['hostname'] = filters.Any(*hostnames)
    for server in (
        query(**query_kwargs)
        .restrict('hostname', 'servertype')
        .order_by('hostname')
    ):
        hosts[server['hostname']] = {
            'hostname': server['hostname'],
            'servertype': server['servertype'],
            'guests': [],
            'cells': [{'column': c} for c in columns],
        }

    # Add guests for the table cells.
    guests = False
    query_kwargs = {'xen_host': filters.Any(*hosts.keys())}
    for server in (
        query(**query_kwargs)
        .restrict('hostname', 'xen_host')
        .order_by('hostname')
    ):
        guests = True
        hosts[server['xen_host']]['guests'].append(server['hostname'])

    # Add cached numerical values to the table cells.
    column_names = [c['name'] for c in columns]
    for numericCache in NumericCache.objects.filter(hostname__in=hosts.keys()):
        if numericCache.template.name in column_names:
            index = column_names.index(numericCache.template.name)
            value = '{:.2f}'.format(numericCache.value)
            hosts[numericCache.hostname]['cells'][index]['value'] = value

    sprite_url = settings.MEDIA_URL + 'graph_sprite/' + collection.name
    template_info.update({
        'columns': columns,
        'hosts': hosts.values(),
        'matched_hostnames': matched_hostnames,
        'understood': understood,
        'error': None,
        'guests': guests,
        'sprite_url': sprite_url,
    })
    return TemplateResponse(request, 'resources/index.html', template_info)


@login_required
def graph_popup(request):
    try:
        hostname = request.GET['hostname']
        graph = request.GET['graph']
    except KeyError:
        return HttpResponseBadRequest('Hostname and graph not supplied')

    # It would be more efficient to filter the collections on the database,
    # but we don't bother because they are unlikely to be more than a few
    # marked as overview.
    for collection in Collection.objects.filter(overview=True):
        servers = collection.query(hostname=hostname)

        if servers:
            table = collection.graph_table(servers.get())
            params = [v2 for k1, v1 in table for k2, v2 in v1][int(graph)]
            url = settings.GRAPHITE_URL + '/render?' + params

            return TemplateResponse(request, 'resources/graph_popup.html', {
                'image': url
            })

    return HttpResponseBadRequest('No graph found')


@login_required
def projects(request):

    counters = {}
    for server in query().restrict(
        'project',
        'servertype',
        'disk_size_gib',
        'memory',
        'num_cpu',
    ):
        if server['project'] not in counters:
            counters[server['project']] = [
                defaultdict(int),   # For servertypes
                0,                  # For disk_size_gib
                0,                  # For memory
                0,                  # For num_cpu
            ]
        counters[server['project']][0][server['servertype']] += 1
        if server.get('disk_size_gib'):
            counters[server['project']][1] += server['disk_size_gib']
        if server.get('memory'):
            counters[server['project']][2] += server['memory']
        if server.get('num_cpu'):
            counters[server['project']][3] += server['num_cpu']

    items = []
    for project in Project.objects.all():
        item = {
            'project_id': project.project_id,
            'subdomain': project.subdomain,
            'responsible_admin': project.responsible_admin.get_full_name(),
            'servertypes': [],
            'disk_size_gib': 0,
            'memory': 0,
            'num_cpu': 0,
        }

        if project.project_id in counters:
            item['servertypes'] = list(counters[project.project_id][0].items())
            item['servertypes'].sort()
            item['disk_size_gib'] = counters[project.project_id][1]
            item['memory'] = counters[project.project_id][2]
            item['num_cpu'] = counters[project.project_id][3]

        items.append(item)

    return TemplateResponse(request, 'resources/projects.html', {
        'projects': items,
    })
