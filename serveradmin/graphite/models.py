"""Serveradmin - Graphite Integration

Copyright (c) 2018 InnoGames GmbH
"""

import json
from string import Formatter
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener
)

from django.db import models
from django.conf import settings

from adminapi.dataset import MultiAttr

from serveradmin.serverdb.models import LOOKUP_ID_VALIDATORS, Attribute

GRAPHITE_ATTRIBUTE_ID = 'graphite_graphs'


class Collection(models.Model):
    """Collection of graphs and values to be shown for the servers"""
    name = models.CharField(max_length=255, validators=LOOKUP_ID_VALIDATORS)
    params = models.TextField(blank=True, help_text="""
        Part of the URL after "?" to GET the graph or the value from
        the Graphite.  It will be concatenated with the params for
        the template and the variation.  Make sure it doesn't include
        any character that doesn't allowed on URL's.  Also do not include "?"
        and do not put "&" at the end.

        The params can include variables inside curly brackets like
        "{hostname}".
        Variables can be any string attribute except multiple ones related to
        the servers.  See Python String Formatting documentation [1] for other
        formatting options.  The dots inside the values are replaced with
        underscores in advance.  If you need to include a brace character in
        the parameters, it can be escaped by doubling: '{{ and }}'.

        Example params:

            width=500&height=500

        [1] https://docs.python.org/2/library/string.html#formatstrings
        """)
    sort_order = models.FloatField(default=0)
    overview = models.BooleanField(default=False, help_text="""
        Marks the collection to be shown on the overview page.  For
        the overview page, sprites will be generated and cached on
        the server in advance to improve the loading time.  {0} will be
        appended to generated URL's to get the images for overview.
        """.format(settings.GRAPHITE_SPRITE_PARAMS))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'graphite_collection'
        ordering = ['sort_order']
        unique_together = [['name', 'overview']]

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self._templates = None     # To cache graph templates
        self._variations = None    # To cache graph variations

    def __str__(self):
        name = self.name
        if self.overview:
            name += ' (overview)'

        return name

    def graph_column(self, server, custom_params=''):
        """Generate graph URL table for a server

        The column is an array of tuples.  The array is ordered.  The tuples
        are used to name the elements.  Example:

            [
                ('CPU Usage', 'target=...'),
                ('Memory Usage', 'target=...'),
            ]
        """
        column = []
        for template in self.template_set.all():
            for foreach_metric in template.foreach(server):
                formatter = AttributeFormatter({
                    'foreach_id': foreach_metric['id'],
                })
                params = self.merged_params((template.params, custom_params))

                name = template.name
                if foreach_metric['text']:
                    name += ' - ' + foreach_metric['text']

                column.append((name, formatter.vformat(params, (), server)))

        return column

    def graph_table(self, server, custom_params=''):
        """Generate graph URL table for a server

        The table is two dimensional array of tuples.  The arrays are
        ordered.  The tuples are used to name the elements.  Example:

            [
                ('CPU Usage', [
                    ('Hourly', 'target=...'),
                    ('Daily', 'target=...'),
                    ('Weekly', 'target=...'),
                ]),
                ('Memory Usage', [
                    ('Hourly', 'target=...'),
                    ('Daily', 'target=...'),
                    ('Weekly', 'target=...'),
                ]),
            ]
        """

        table = []
        for template in self.template_set.all():
            for foreach_metric in template.foreach(server):
                column = []
                for variation in self.variation_set.all():
                    formatter = AttributeFormatter({
                        'foreach_id': foreach_metric['id'],
                        'summarize_interval': variation.summarize_interval,
                    })
                    params = self.merged_params((variation.params,
                                                 template.params,
                                                 custom_params))
                    column.append((variation.name,
                                   formatter.vformat(params, (), server)))

                name = template.name
                if foreach_metric['text']:
                    name += ' - ' + foreach_metric['text']

                table.append((name, column))

        return table

    def merged_params(self, other_params):
        """Get merged and cleaned URL parameters"""
        params = self.params
        for p in other_params:
            if p:
                params += '&' + p

        for r in (' ', '\t', '\n', '\r', '\v'):
            params = params.replace(r, '')

        return params


class Numeric(models.Model):
    """Templates in the collections"""
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE,
        limit_choices_to={'overview': True},
    )
    params = models.TextField(
        blank=True, help_text="Same as the params of the collections"
    )
    sort_order = models.FloatField(default=0)
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE,
        limit_choices_to={
            'multi': False,
            'type': 'number',
            'readonly': True,
        }
    )

    class Meta:
        db_table = 'graphite_numeric'
        ordering = ['sort_order']
        unique_together = [['collection', 'attribute']]

    def __str__(self):
        return self.attribute_id


class Relation(models.Model):
    """Templates in the collections"""
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE,
        limit_choices_to={'overview': True}
    )
    sort_order = models.FloatField(default=0)
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            type__in=['relation', 'reverse', 'supernet', 'domain']
        )
    )

    class Meta:
        db_table = 'graphite_relation'
        ordering = ['sort_order']
        unique_together = [['collection', 'attribute']]

    def __str__(self):
        return self.attribute_id


class Template(models.Model):
    """Templates in the collections"""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, validators=LOOKUP_ID_VALIDATORS)
    params = models.TextField(blank=True, help_text="""
        Same as the params of the collections.
        """)
    sort_order = models.FloatField(default=0)
    description = models.TextField(blank=True)
    foreach_path = models.CharField(max_length=256, blank=True, help_text="""
        Generates multiple graphs from the same template.  Variables can be
        used like "params".  It will be a variable for the "params" that can
        be used as {foreach_id}.  Example value:

            servers.{hostname}.system.cpu.*
        """)

    class Meta:
        db_table = 'graphite_template'
        ordering = ['sort_order']
        unique_together = [['collection', 'name']]

    def __str__(self):
        return self.name

    def foreach(self, server):
        """Helper function to iterate Graphite metrics using foreach_path

        We will return an empty element even though foreach_path is not set
        for convenience of the caller.
        """

        if self.foreach_path:
            formatter = AttributeFormatter()
            params = formatter.vformat(
                'query=' + self.foreach_path, (), server
            )

            password_mgr = HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(
                None,
                settings.GRAPHITE_URL,
                settings.GRAPHITE_USER,
                settings.GRAPHITE_PASSWORD,
            )
            auth_handler = HTTPBasicAuthHandler(password_mgr)
            url = '{0}/metrics/find?{1}'.format(
                settings.GRAPHITE_URL, params
            )
            with build_opener(auth_handler).open(url) as response:
                return json.loads(response.read().decode())

        return [{
            'id': '',
            'leaf': 0,
            'context': {},
            'text': '',
            'expandable': 0,
            'allowChildren': 0,
        }]


class Variation(models.Model):
    """Variation to render the templates
    """

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, validators=LOOKUP_ID_VALIDATORS)
    params = models.TextField(blank=True, help_text="""
        Same as the params of the collections.
        """)
    sort_order = models.FloatField(default=0)
    summarize_interval = models.CharField(max_length=255, help_text="""
        Interval string that makes sense to use on the summarize() function on
        the Graphite for this variation.  It can be used in the params as
        {summarize_interval}.
        """)

    class Meta:
        db_table = 'graphite_variation'
        ordering = ['sort_order']
        unique_together = [['collection', 'name']]

    def __str__(self):
        return self.name


class AttributeFormatter(Formatter):
    """Custom Formatter to replace variables on URL parameters

    Attributes and hostname can be used on the params supplied by the templates
    and the variations.  Graphite uses dots as the separator.  We chose
    to replace them with underscores.  We will apply it to all variables
    to be replaced..

    Replacing the hostname variable is easy.  Replacing variables for
    attributes requires to override the get_value() method of the base class
    which is only capable of returning the value of the given dictionary.
    To support multiple attributes, we are going to have arrays in the given
    dictionary.  Also, we would like to use all values only once to make
    a sensible use of multiple attributes.

    Furthermore, we don't want to raise an error.  We will just return
    an empty string, if the key doesn't exists.  We will cycle and use
    the same multiple attributes again, if we run out of them.
    """

    def __init__(self, variables={}):
        Formatter.__init__(self)
        self._variables = variables
        self._last_item_ids = {}

    def get_value(self, key, args, server):
        if key in self._variables:
            return self._variables[key]

        if key not in server:
            return ''

        if not isinstance(server[key], MultiAttr):
            return format_attribute_value(str(server[key]))

        # Initialize the last used id for the key.
        if key not in self._last_item_ids:
            self._last_item_ids[key] = 0
            return format_attribute_value(str(server[key][0]))

        # Increment the last used id for the key.
        self._last_item_ids[key] += 1

        # Cycle the last used id for the key.
        self._last_item_ids[key] %= len(server[key])

        return format_attribute_value(server[key][self._last_item_ids[key]])


def format_attribute_value(value):
    """Apply random rules we have to the attribute values"""
    # XXX This function is a terrible temporary hack that needs to go away
    for suffix in ['.ig.local', '.innogames.net']:
        if value.endswith(suffix):
            value = value[:-len(suffix)]
    return value.replace('.', '_')
