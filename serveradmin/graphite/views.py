import urllib
from string import Formatter

from django.shortcuts import render
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings

from adminapi.utils.parse import parse_query
from serveradmin.graphite.models import *
from serveradmin.dataset import query, filters, DatasetError
from serveradmin.serverdb.models import AttributeValue, ServerType, Segment
from serveradmin.servermonitor.getinfo import get_information

@login_required
@ensure_csrf_cookie
def index(request):
    """Index page of the Graphite tab"""

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
                    'understood': understood,
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
    return TemplateResponse(request, 'graphite/index.html', template_info)


@login_required
@ensure_csrf_cookie
def graph_table(request):

    try:
        hostname = request.GET['hostname']
    except KeyError:
        return HttpResponseBadRequest('You have to provide a hostname')

    #
    # Prepare the dictionary to format URL's
    #
    # String attributes can be used on the params supplied by the Graph
    # templates.  We will prepare a dictionary with them for ease of use.
    # Also, we need to replace hostname variables inside the params as
    # the templates will be defined for many servers.  Dots on the hostnames
    # are replaced by underscores on the Graphite.
    attribute_values = AttributeValue.objects.filter(server__hostname=hostname,
                                                     attrib__type='string',
                                                     attrib__multi=False)
    formatting_dict = dict((a.attrib.name, a.value) for a in attribute_values)
    formatting_dict['hostname'] = hostname.replace('.', '_')

    #
    # Generate graph table
    #
    # Graph table is two dimensional array of tuples.  The arrays are ordered.
    # The tuples are used to name the elements.  Example:
    #
    #   [
    #       ('CPU Usage', [
    #           ('Hourly', 'http://graphite.innogames.de/render?target=...'),
    #           ('Daily', 'http://graphite.innogames.de/render?target=...'),
    #           ('Weekly', 'http://graphite.innogames.de/render?target=...'),
    #       ]),
    #       ('Memory Usage', [
    #           ('Hourly', 'http://graphite.innogames.de/render?target=...'),
    #           ('Daily', 'http://graphite.innogames.de/render?target=...'),
    #           ('Weekly', 'http://graphite.innogames.de/render?target=...'),
    #       ]),
    #   ]
    #
    # We could filter the groups on the database, but we don't bother because
    # they are unlikely to be more than a few.
    #
    graph_table = []
    for group in GraphGroup.objects.all():
        if formatting_dict.get(group.attrib.name) == group.attrib_value:
            for template in GraphTemplate.objects.filter(graph_group=group):
                params = Formatter().vformat(template.params, (), formatting_dict)
                base_url = settings.GRAPHITE_URL + '/render?'

                column = []
                for time_range in GraphTimeRange.objects.filter(graph_group=group):
                    params = '&'.join((group.params,
                                       time_range.params,
                                       template.params))
                    params = Formatter().vformat(params, (), formatting_dict)

                    column.append((time_range.name,
                                   settings.GRAPHITE_URL + '/render?' + params))

                graph_table.append((template.name, column))

    return TemplateResponse(request, 'graphite/graph_table.html', {
        'hostname': hostname,
        'graph_table': graph_table,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })
