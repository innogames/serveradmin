from django.http import HttpResponse, HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

import django_urlauth.utils

from adminapi.utils.parse import parse_query
from adminapi.dataset.base import MultiAttr
from serveradmin.graphite.models import Collection, NumericCache
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.serverdb.models import ServerType, Segment

@ensure_csrf_cookie
def index(request):
    """Index page of the Graphite tab
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
    # structure, we will just get one of them for the table headers.
    collection = Collection.objects.filter(overview=True)[0]
    names = []
    for template in collection.template_set.all():
        if template.numeric_value:
            names.append(unicode(template))
        else:
            for variation in collection.variation_set.all():
                names.append(unicode(template) + ' ' + unicode(variation))

    hosts = {}
    query_kwargs = {'physical_server': True, 'cancelled': False}
    if len(hostnames) > 0:
        query_kwargs['hostname'] = filters.Any(*hostnames)
    for server in query(**query_kwargs).restrict('hostname', 'servertype'):
        guests = query(xen_host=server['hostname']).restrict('hostname')
        hosts[server['hostname']] = {
            'hostname': server['hostname'],
            'servertype': server['servertype'],
            'guests': [g['hostname'] for g in guests],
            'cells': [],
        }
        for name in names:
            hosts[server['hostname']]['cells'].append({'numeric_value': False})

    for numericCache in NumericCache.objects.filter(hostname__in=hosts.keys()):
        index = names.index(unicode(numericCache.template))
        hosts[numericCache.hostname]['cells'][index]['numeric_value'] = True
        hosts[numericCache.hostname]['cells'][index]['value'] = numericCache.value

    offset = settings.GRAPHITE_SPRITE_WIDTH + settings.GRAPHITE_SPRITE_SPACING
    for host in hosts.values():
        index = 0
        for cell in host['cells']:
            if not cell['numeric_value']:
                cell['graph_index'] = index
                cell['sprite_offset'] = index * offset
                index += 1

    template_info.update({
        'names': names,
        'hosts': hosts.values(),
        'matched_hostnames': matched_hostnames,
        'understood': understood,
        'error': None,
        'GRAPHITE_SPRITE_URL': settings.GRAPHITE_SPRITE_URL,
    })
    return TemplateResponse(request, 'graphite/index.html', template_info)

@login_required
@ensure_csrf_cookie
def graph_table(request):
    """Graph table page

    We will accept all GET parameters and pass them to Graphite.
    """

    hostnames = [h for h in request.GET.getlist('hostname') if h]
    if len(hostnames) == 0:
        return HttpResponseBadRequest('You have to provide at least one hostname')

    # For convenience we will cache the servers in a dictionary.
    servers = {}
    for hostname in hostnames:
        servers[hostname] = query(hostname=hostname).get()

    # Find the collections which are related with all of the hostnames
    collections = []
    for collection in Collection.objects.all():
        for hostname in hostnames:
            if collection.attrib.name not in servers[hostname]:
                break   # The server hasn't got this attribute at all.
            value = servers[hostname][collection.attrib.name]
            if isinstance(value, MultiAttr):
                if collection.attrib_value not in [str(v) for v in value]:
                    break   # The server hasn't got this attribute value.
            else:
                if collection.attrib_value != str(value):
                    break   # The server attribute is not equal.
        else:
            collections.append(collection)

    # Prepare the graph descriptions
    descriptions = []
    for collection in collections:
        for template in collection.template_set.all():
            descriptions += ([(template.name, template.description)] * len(hostnames))

    # Prepare the graph tables for all hosts
    graph_tables = []
    for hostname in hostnames:
        graph_table = []
        if request.GET.get('action') == 'Submit':
            custom_params = request.GET.urlencode()
            for collection in collections:
                column = collection.graph_column(servers[hostname], custom_params)
                graph_table += [(k, [('Custom', v)]) for k, v in column]
        else:
            for collection in collections:
                graph_table += collection.graph_table(servers[hostname])
        graph_tables.append(graph_table)

    if len(hostname) > 1:
        # Add hostname to the titles
        for order, hostname in enumerate(hostnames):
            graph_tables[order] = [(k + ' on ' + hostname, v)
                                   for k, v in graph_tables[order]]

        # Combine them
        graph_table = []
        for combined_tables in zip(*graph_tables):
            graph_table += list(combined_tables)

    return TemplateResponse(request, 'graphite/graph_table.html', {
        'hostnames': hostnames,
        'descriptions': descriptions,
        'GRAPHITE_URL': settings.GRAPHITE_URL,
        'graph_table': graph_table,
        'token': django_urlauth.utils.new_token(request.user.username,
                                                settings.GRAPHITE_SECRET),
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
        'from': request.GET.get('from', '-24h'),
        'until': request.GET.get('until', 'now'),
    })

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

            return TemplateResponse(request, 'graphite/graph_popup.html', {
                'hostname': hostname,
                'graph': graph,
                'image': url
            })
