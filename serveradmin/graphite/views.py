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
def graph_table(request, hostname):

    #
    # Optional parameters
    #
    # We will accept all GET parameters and pass them to Graphite.  We only
    # care that there are any GET parameters or not.  If there are in custom
    # graph mode.
    #
    custom_params = request.GET.urlencode()

    #
    # Prepare the dictionary of attributes
    #
    # For convenience we will create a dictionary of attributes and store
    # array of values in it.  They will be used to filter the graphs and
    # to format the URL parameters of the graphs.
    #
    attribute_dict = {}
    for row in AttributeValue.objects.filter(server__hostname=hostname):
        if row.attrib.name not in attribute_dict:
            attribute_dict[row.attrib.name] = [row.value]
        else:
            attribute_dict[row.attrib.name].append(row.value)

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

        if (group.attrib.name in attribute_dict and
            group.attrib_value in attribute_dict[group.attrib.name]):

            for template in GraphTemplate.objects.filter(graph_group=group):

                column = []
                for variation in GraphVariation.objects.filter(
                        graph_group=group,
                        custom_mode=(custom_params != '')
                    ):

                    formatter = AttributeFormatter(hostname)
                    params = '&'.join((custom_params, group.params,
                                       variation.params, template.params))
                    params = formatter.vformat(params, (), attribute_dict)

                    column.append((variation.name,
                                   settings.GRAPHITE_URL + '/render?' + params))

                graph_table.append((template.name, column))

    return TemplateResponse(request, 'graphite/graph_table.html', {
        'hostname': hostname,
        'graph_table': graph_table,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
        'from': request.GET.get('from', ''),
        'until': request.GET.get('until', ''),
    })

#
# Attribute formatter class
#
# Attributes and hostname can be used on the params supplied by the Graph
# templates and variations.  Replacing the variables for hostname is easy.
# We only need to replace the dots on the hostname with underscores as
# it is done on Graphite.
#
# Replacing variables for attributes requires to override the get_value()
# method of the base class which is only capable of returning the value
# of the given dictionary.  To support multiple attributes we have arrays
# in the given dictionary.  Also, we would like to use all values only once
# to make a sensible use of multiple attributes.
#
class AttributeFormatter(Formatter):
    """Custom Formatter to replace variables on URL parameters"""

    def __init__(self, hostname):
        Formatter.__init__(self)
        self.__hostname = hostname.replace('.', '_')
        self.__last_item_ids = {}

    def get_value(self, key, args, kwds):
        if key == 'hostname':
            return self.__hostname

        # Initialize or increment the last used id for the key.
        if key not in self.__last_item_ids:
            self.__last_item_ids[key] = 0
        else:
            self.__last_item_ids[key] += 1

        # It will raise an error if there is no value.
        return kwds[key][self.__last_item_ids[key]]
