from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

import django_urlauth.utils

from adminapi.utils.parse import parse_query
from serveradmin.graphite.models import Collection, NumericCache
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.serverdb.models import ServerType, Segment

@ensure_csrf_cookie
def index(request):
    """The hardware resources page
    """

    term = request.GET.get('term', request.session.get('term', ''))

    template_info = {
        'search_term': term,
        'segments': Segment.objects.order_by('segment'),
        'servertypes': ServerType.objects.order_by('name')
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

    # All of the collections marked as overview should have the same
    # structure, we will just get one of them for the table structure.
    collection = Collection.objects.filter(overview=True)[0]
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

    hosts = {}
    query_kwargs = {'physical_server': True, 'cancelled': False}
    if len(hostnames) > 0:
        query_kwargs['hostname'] = filters.Any(*hostnames)
    for server in query(**query_kwargs).restrict('hostname', 'servertype'):
        hosts[server['hostname']] = {
            'hostname': server['hostname'],
            'servertype': server['servertype'],
            'guests': [],
            'columns': list(columns),
        }

    # Add guests for the table cells.
    query_kwargs = {'xen_host': filters.Any(*hosts.keys()), 'cancelled': False}
    for server in query(**query_kwargs).restrict('hostname', 'xen_host'):
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
                'hostname': hostname,
                'graph': graph,
                'image': url
            })
