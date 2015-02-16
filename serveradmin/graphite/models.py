from string import Formatter

from django.db import models
from django.conf import settings

from serveradmin.serverdb.models import Attribute, AttributeValue

class GraphManager(object):
    """A helper class to get the graphs
    """

    def __init__(self):
        self._groups = None    # To cache all graph groups
        self._overview_group = None # To cache the special overview group

    def graph_table(self, hostname, custom_params=''):

        # For convenience we will create a dictionary of attributes and store
        # array of values in it.  They will be used to filter the graphs and
        # to format the URL parameters of the graphs.
        attribute_dict = {}
        for row in AttributeValue.objects.filter(server__hostname=hostname):
            if row.attrib.name not in attribute_dict:
                attribute_dict[row.attrib.name] = [row.value]
            else:
                attribute_dict[row.attrib.name].append(row.value)

        # We could filter the groups on the database, but we don't bother
        # because they are unlikely to be more than a few.
        if self._groups == None:
            self._groups = list(GraphGroup.objects.all())

        graph_table = []
        for group in self._groups:
            if group.attrib.name not in attribute_dict:
                continue    # The server hasn't got this attribute at all.
            if group.attrib_value not in attribute_dict[group.attrib.name]:
                continue    # The server hasn't got this attribute value.

            if custom_params == '':
                graph_table += group.graph_table(hostname, attribute_dict)
            else:
                column = group.graph_column(hostname, attribute_dict,
                                            custom_params)
                graph_table += [(k, [('Custom', v)]) for k, v in column]

        return graph_table

    overview_attrib_name = 'physical_server'
    overview_attrib_value = 1

    def overview_graph_group(self):
        """Caches and returns the special hardcoded graph group for overview

        There must be a group with this attribute and value.
        """

        if self._overview_group == None:
            self._overview_group = GraphGroup.objects.get(
                    attrib__name=self.overview_attrib_name,
                    attrib_value=self.overview_attrib_value
                )

        return self._overview_group

class GraphGroup(models.Model):
    """Graph groups to be shown for the servers with defined attribute
    """

    graph_group_id = models.AutoField(primary_key=True)
    attrib = models.ForeignKey(Attribute, verbose_name='attribute')
    attrib_value = models.CharField(max_length=1024,
                                    verbose_name='attribute value')
    params = models.CharField(max_length=1024, blank=True, help_text="""
        Part of the URL after "?" to GET the graph from the Graphite.  It
        will be concatenated with the params for the graph template and graph
        variation.  Make sure it doesn't include any character that doesn't
        allowed on URL's.  Also do not include "?" and do not put "&" at
        the end.  Example parameters:

        The params can include variables inside curly brackets like "{hostname}".
        Variables can be any string attribute except multiple ones related to
        the servers.  See Python String Formatting documentation [1] for other
        formatting options.

        Example params:

            width=500&height=500

        [1] https://docs.python.org/2/library/string.html#formatstrings
        """)

    class Meta:
        db_table = 'graph_group'
        ordering = ('graph_group_id', )
        unique_together = (('attrib', 'attrib_value'), )

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._templates = None     # To cache graph templates
        self._variations = None    # To cache graph variations

    def __unicode__(self):
        return unicode(self.attrib) + ': ' + self.attrib_value

    def get_templates(self):
        """Cache and return the graph templates
        """

        if self._templates == None:
            self._templates = list(GraphTemplate.objects.filter(graph_group=self))

        return self._templates

    def get_variations(self):
        """Cache and return the graph variations
        """

        if self._variations == None:
            self._variations = list(GraphVariation.objects.filter(graph_group=self))

        return self._variations

    def graph_column(self, hostname, attribute_dict={}, custom_params=''):
        """Generate graph URL table for a server

        Graph table is an array of tuples.  The array is ordered.  The tuples
        are used to name the elements.  Example:

            [
                ('CPU Usage', 'http://graphite.innogames.de/render?target=...'),
                ('Memory Usage', 'http://graphite.innogames.de/render?target=...'),
            ]
        """

        column = []
        for template in self.get_templates():
            formatter = AttributeFormatter(hostname)
            params = '&'.join((self.params, template.params, custom_params))
            params = formatter.vformat(params, (), attribute_dict)

            column.append((template.name,
                           settings.GRAPHITE_URL + '/render?' + params))

        return column

    def graph_table(self, hostname, attribute_dict={}, custom_params=''):
        """Generate graph URL table for a server

        Graph table is two dimensional array of tuples.  The arrays are
        ordered.  The tuples are used to name the elements.  Example:

            [
                ('CPU Usage', [
                    ('Hourly', 'http://graphite.innogames.de/render?target=...'),
                    ('Daily', 'http://graphite.innogames.de/render?target=...'),
                    ('Weekly', 'http://graphite.innogames.de/render?target=...'),
                ]),
                ('Memory Usage', [
                    ('Hourly', 'http://graphite.innogames.de/render?target=...'),
                    ('Daily', 'http://graphite.innogames.de/render?target=...'),
                    ('Weekly', 'http://graphite.innogames.de/render?target=...'),
                ]),
            ]
        """

        table = []
        for template in self.get_templates():
            column = []
            for variation in self.get_variations():
                formatter = AttributeFormatter(hostname)
                params = '&'.join((self.params, variation.params,
                                   template.params, custom_params))
                params = formatter.vformat(params, (), attribute_dict)

                column.append((variation.name,
                               settings.GRAPHITE_URL + '/render?' + params))

            table.append((template.name, column))

        return table

class GraphTemplate(models.Model):
    """Graph templates of the graph group
    """

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    params = models.CharField(max_length=1024, blank=True, help_text="""
        Same as the params of the graph groups.
        """)
    sort_order = models.FloatField(default=0)

    class Meta:
        db_table = 'graph_template'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name

class GraphVariation(models.Model):
    """Graph variation to render the graph templates
    """

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    params = models.CharField(max_length=1024, blank=True, help_text="""
        Same as the params of the graph groups.
        """)
    sort_order = models.FloatField(default=0)

    class Meta:
        db_table = 'graph_variation'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name

class AttributeFormatter(Formatter):
    """Custom Formatter to replace variables on URL parameters

    Attributes and hostname can be used on the params supplied by the Graph
    templates and variations.  Replacing the variables for hostname is easy.
    We only need to replace the dots on the hostname with underscores as
    it is done on Graphite.

    Replacing variables for attributes requires to override the get_value()
    method of the base class which is only capable of returning the value
    of the given dictionary.  To support multiple attributes we have arrays
    in the given dictionary.  Also, we would like to use all values only once
    to make a sensible use of multiple attributes.

    Furthermore, we don't want to raise an error.  We will just return
    an empty string, if the key doesn't exists.  We will cycle and use
    the same multiple attributes again, if we run out of them.
    """

    def __init__(self, hostname):
        Formatter.__init__(self)
        self._hostname = hostname.replace('.', '_')
        self._last_item_ids = {}

    def get_value(self, key, args, kwds):
        if key == 'hostname':
            return self._hostname

        if key not in kwds:
            return ''

        # Initialize the last used id for the key.
        if key not in self._last_item_ids:
            self._last_item_ids[key] = 0
            return kwds[key][0]

        # Increment the last used id for the key.
        self._last_item_ids[key] += 1
        
        # Cycle the last used id for the key.
        self._last_item_ids[key] %= len(kwds[key])

        return kwds[key][self._last_item_ids[key]]
