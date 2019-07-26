"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from adminapi.datatype import DatatypeError
from adminapi.filters import Any
from adminapi.parse import parse_query
from serveradmin.dataset import Query
from serveradmin.graphite.models import GRAPHITE_ATTRIBUTE_ID, Collection
from serveradmin.graphite.views import graph


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
        return HttpResponseBadRequest('No matching current collection')

    template_info = {
        'search_term': term,
        'collections': collections,
        'current_collection': current_collection.id,
    }

    # TODO: Generalize this part using the relations
    hostnames = []
    matched_hostnames = []
    if term:
        try:
            query_args = parse_query(term)
            host_query = Query(query_args, ['hostname', 'hypervisor'])
            for host in host_query:
                matched_hostnames.append(host['hostname'])
                if host.get('hypervisor'):
                    hostnames.append(host['hypervisor'])
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
        except (DatatypeError, ValidationError) as error:
            template_info.update({
                'error': str(error)
            })
            return TemplateResponse(
                request, 'resources/index.html', template_info
            )
    else:
        understood = repr(Query({}))

    variations = list(current_collection.variation_set.all())
    columns = []
    attribute_ids = ['hostname', 'servertype']
    graph_index = 0
    sprite_width = settings.GRAPHITE_SPRITE_WIDTH
    for template in current_collection.template_set.all():
        for variation in variations:
            columns.append({
                'name': str(template) + ' ' + str(variation),
                'type': 'graph',
                'graph_index': graph_index,
                'sprite_offset': graph_index * sprite_width,
            })
            graph_index += 1
    for numeric in current_collection.numeric_set.all():
        columns.append({
            'name': str(numeric),
            'type': 'numeric',
        })
        attribute_ids.append(numeric.attribute_id)
    for relation in current_collection.relation_set.all():
        columns.append({
            'name': str(relation),
            'type': 'relation',
        })
        attribute_ids.append(relation.attribute_id)

    hosts = OrderedDict()
    filters = {GRAPHITE_ATTRIBUTE_ID: collection.name}
    if len(hostnames) > 0:
        filters['hostname'] = Any(*hostnames)
    for server in Query(filters, attribute_ids):
        hosts[server['hostname']] = dict(server)

    sprite_url = settings.MEDIA_URL + 'graph_sprite/' + collection.name
    template_info.update({
        'columns': columns,
        'hosts': hosts.values(),
        'matched_hostnames': matched_hostnames,
        'understood': understood,
        'error': None,
        'sprite_url': sprite_url,
    })
    return TemplateResponse(request, 'resources/index.html', template_info)


@login_required
def graph_popup(request):
    try:
        hostname = request.GET['hostname']
        graph_id = request.GET['graph']
    except KeyError:
        return HttpResponseBadRequest('Hostname and graph not supplied')

    # It would be more efficient to filter the collections on the database,
    # but we don't bother because they are unlikely to be more than a few
    # marked as overview.
    for collection in Collection.objects.filter(overview=True):
        servers = list(Query({
            GRAPHITE_ATTRIBUTE_ID: collection.name,
            'hostname': hostname,
        }))
        if servers:
            table = collection.graph_table(servers[0])
            params = [v2 for k1, v1 in table for k2, v2 in v1][int(graph_id)]
            url = reverse(graph) + '?' + params

            return TemplateResponse(request, 'resources/graph_popup.html', {
                'image': url
            })

    return HttpResponseBadRequest('No graph found')
