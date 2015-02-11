from django.db import models

from serveradmin.serverdb.models import Attribute

class GraphGroup(models.Model):
    """Graph groups to be shown for the servers with defined attribute"""

    graph_group_id = models.AutoField(primary_key=True)
    attrib = models.ForeignKey(Attribute, verbose_name='attribute')
    attrib_value = models.CharField(max_length=1024,
                                    verbose_name='attribute value')
    params = models.CharField(max_length=1024, blank=True, help_text='''
Part of the URL after "?" to GET the graph from the Graphite.  It will be
concatenated with the params for the graph template and graph variation.
Make sure it doesn't include any character that doesn't allowed on URL's.
Also do not include "?" and do not put "&" at the end.  Example parameters:

The params can include variables inside curly brackets like "{hostname}".
Variables can be any string attribute except multiple ones related to
the servers.  See Python String Formatting documentation [1] for other
formatting options.

Example params:

    width=500&height=500

[1] https://docs.python.org/2/library/string.html#formatstrings
''')

    class Meta:
        db_table = 'graph_group'
        ordering = ('graph_group_id', )

    def __unicode__(self):
        return unicode(self.attrib) + ': ' + self.attrib_value

class GraphTemplate(models.Model):
    """Graph templates of the graph group"""

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    params = models.CharField(max_length=1024, blank=True, help_text='''
Same as the params of the graph groups.
''')
    sort_order = models.FloatField(default=0)

    class Meta:
        db_table = 'graph_template'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name

class GraphVariation(models.Model):
    """Graph variation to render the graph templates"""

    graph_group = models.ForeignKey(GraphGroup)
    name = models.CharField(max_length=64)
    custom_mode = models.BooleanField(default=False)
    params = models.CharField(max_length=1024, blank=True, help_text='''
Same as the params of the graph groups.
''')
    sort_order = models.FloatField(default=0)

    class Meta:
        db_table = 'graph_variation'
        ordering = ('sort_order', )
        unique_together = (('graph_group', 'name'), )

    def __unicode__(self):
        return self.name
