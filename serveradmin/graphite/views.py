"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener
)

from django.http import (
    HttpResponse, HttpResponseBadRequest, HttpResponseServerError
)
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

from adminapi.dataset import DatasetError, MultiAttr
from adminapi.filters import Any
from serveradmin.graphite.models import (
    GRAPHITE_ATTRIBUTE_ID,
    Collection,
    format_attribute_value,
)
from serveradmin.dataset import Query


@login_required     # NOQA: C901
@ensure_csrf_cookie
def graph_table(request):
    """Graph table page"""
    hostnames = [h for h in request.GET.getlist('hostname', []) if h]
    object_ids = [o for o in request.GET.getlist('object_id', []) if o]
    if len(hostnames) == 0 and len(object_ids) == 0:
        return HttpResponseBadRequest('No hostname or object_id provided')

    # For convenience we will cache the servers in a dictionary.
    servers = {s['hostname']: s for s in
               Query({'hostname': Any(*hostnames)}, None)}
    servers.update({s['hostname']: s for s in
                    Query({'object_id': Any(*object_ids)}, None)})

    # Find the collections which are related with all of the hostnames.
    # If there are two collections with same match, use only the one which
    # is not an overview.
    collections = []
    for collection in Collection.objects.order_by('overview', 'sort_order'):
        if any(collection.name == c.name for c in collections):
            continue
        for hostname in servers.keys():
            if GRAPHITE_ATTRIBUTE_ID not in servers[hostname]:
                break   # The server hasn't got this attribute at all.
            value = servers[hostname][GRAPHITE_ATTRIBUTE_ID]
            assert isinstance(value, MultiAttr)
            if not any(collection.name == v for v in value):
                break   # The server hasn't got this attribute value.
        else:
            collections.append(collection)

    # Prepare the graph descriptions
    descriptions = []
    for collection in collections:
        for template in collection.template_set.all():
            descriptions += (
                [(template.name, template.description)] * len(servers.keys())
            )

    # Prepare the graph tables for all hosts
    graph_tables = []
    for hostname in servers.keys():
        graph_table = []
        if request.GET.get('action') == 'Submit':
            custom_params = request.GET.urlencode()
            for collection in collections:
                column = collection.graph_column(
                    servers[hostname], custom_params
                )
                graph_table += [(k, [('Custom', v)]) for k, v in column]
        else:
            for collection in collections:
                graph_table += collection.graph_table(servers[hostname])
        graph_tables.append(graph_table)

    grafana_link_params = '?'
    if len(hostname) > 1:
        # Add hostname to the titles
        for order, hostname in enumerate(servers.keys()):
            graph_tables[order] = [
                (k + ' on ' + hostname, v) for k, v in graph_tables[order]
            ]
            grafana_link_params += 'var-SERVER={}&'.format(
                format_attribute_value(hostname)
            )

        # Combine them
        graph_table = []
        for combined_tables in zip(*graph_tables):
            graph_table += list(combined_tables)

    return TemplateResponse(request, 'graphite/graph_table.html', {
        'hostnames': servers.keys(),
        'descriptions': descriptions,
        'graph_table': graph_table,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
        'from': request.GET.get('from', '-24h'),
        'until': request.GET.get('until', 'now'),
        'grafana_link': settings.GRAFANA_DASHBOARD + grafana_link_params
    })


@login_required
@ensure_csrf_cookie
def graph(request):
    """Proxy Graphite graphs

    We don't want to bother the user with authenticating to Graphite.
    Instead, here we download the graph using our credentials and pass
    it to the user.
    """
    password_mgr = HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(
        None,
        settings.GRAPHITE_URL,
        settings.GRAPHITE_USER,
        settings.GRAPHITE_PASSWORD,
    )
    auth_handler = HTTPBasicAuthHandler(password_mgr)
    url = '{0}/render?{1}'.format(
        settings.GRAPHITE_URL, request.GET.urlencode()
    )

    # If the Graphite server fails, we would return proper server error
    # to the user instead of failing.  This is not really a matter for
    # the user as they would get a 500 in any case, but it is a matter for
    # the server.  We expect any kind of IO error in here, but the socket
    # errors are more likely to happen.  Graphite has the tendency to return
    # empty result with 200 instead of proper error codes.
    try:
        with build_opener(auth_handler).open(url) as response:
            return HttpResponse(response.read(), content_type='image/png')
    except IOError as error:
        return HttpResponseServerError(str(error))
