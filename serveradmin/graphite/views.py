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
