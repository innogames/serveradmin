"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousOperation
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.csrf import ensure_csrf_cookie

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

    # If a graph collection was specified, use it. Otherwise use the first one
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
        query_args = parse_query(term)
        # @TODO: This is the slowest part here unfortunately the Query object
        # does not support pagination yet so there is nothing to speed this
        # up right now.
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
    else:
        understood = repr(Query({}))

    variations = list(current_collection.variation_set.all())
    columns = []
    columns_selected = request.GET.getlist(
        'columns', request.session.get('resources_columns', []))
    request.session['resources_columns'] = columns_selected
    attribute_ids = ['hostname', 'servertype']
    graph_index = 0
    sprite_width = settings.GRAPHITE_SPRITE_WIDTH
    for template in current_collection.template_set.all():
        for variation in variations:
            name = str(template) + ' ' + str(variation)
            columns.append({
                'name': name,
                'type': 'graph',
                'graph_index': graph_index,
                'sprite_offset': graph_index * sprite_width,
                'visible': slugify(name) in columns_selected,
            })
            graph_index += 1
    for numeric in current_collection.numeric_set.all():
        columns.append({
            'name': str(numeric),
            'type': 'numeric',
            'visible': slugify(numeric) in columns_selected,
        })
        attribute_ids.append(numeric.attribute_id)
    for relation in current_collection.relation_set.all():
        columns.append({
            'name': str(relation),
            'type': 'relation',
            'visible': slugify(relation) in columns_selected,
        })
        attribute_ids.append(relation.attribute_id)

    hosts = OrderedDict()
    filters = {GRAPHITE_ATTRIBUTE_ID: collection.name}
    if len(hostnames) > 0:
        filters['hostname'] = Any(*hostnames)
        for server in Query(filters, attribute_ids):
            hosts[server['hostname']] = dict(server)

    page = abs(int(request.GET.get('page', 1)))
    per_page = int(request.GET.get(
        'per_page', request.session.get('resources_per_page', 8)))

    # Save settings in session
    request.session['resources_per_page'] = per_page

    try:
        hosts_pager = Paginator(list(hosts.values()), per_page)

        # Term or data in DB has changed
        if page > hosts_pager.num_pages:
            page = 1

        hosts_pager = hosts_pager.page(page)
    except (PageNotAnInteger, EmptyPage):
        raise SuspiciousOperation('{} is not a valid!'.format(page))

    sprite_url = settings.MEDIA_URL + 'graph_sprite/' + collection.name
    template_info.update({
        'columns': columns,
        'hosts': hosts_pager,
        'page': page,
        'per_page': per_page,
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
