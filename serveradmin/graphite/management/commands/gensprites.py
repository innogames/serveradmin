import urllib2
from PIL import Image
from io import BytesIO

from django.core.management.base import NoArgsCommand
from django.core.cache import cache
from django.conf import settings

import django_urlauth.utils
from serveradmin.graphite.models import GraphGroup

class Command(NoArgsCommand):
    """Generate sprites from the overview graphics
    """

    help = __doc__

    def handle_noargs(self, **kwargs):
        """The entry point of the command
        """

        # We will make sure to generate a single sprite for a single hostname.
        done_servers = set()
        for graph_group in GraphGroup.objects.filter(overview=True):
            for server in graph_group.query():
                if server not in done_servers:
                    self.generate_sprite(graph_group, server)
                    done_servers.add(server)

    def generate_sprite(self, graph_group, server):
        """The main function
        """

        table = graph_group.graph_table(server,
                                custom_params=settings.GRAPHITE_SPRITE_PARAMS)
        graphs = [v2 for k1, v1 in table for k2, v2 in v1]
        sprite_width = (len(graphs) * settings.GRAPHITE_SPRITE_WIDTH +
                        (len(graphs) - 1) * settings.GRAPHITE_SPRITE_SPACING)
        spriteimg = Image.new('RGB', (sprite_width,
                                      settings.GRAPHITE_SPRITE_HEIGHT),
                                      (255,) * 3)
        opener = urllib2.build_opener()
        offset = 0

        for graph in graphs:
            token = django_urlauth.utils.new_token('serveradmin',
                                                   settings.GRAPHITE_SECRET)
            url = (settings.GRAPHITE_URL + '/render?' + graph + '&' +
                   '__auth_token=' + token)

            try:
                tmpimg = BytesIO(opener.open(url).read())
            except urllib2.HTTPError as error:
                print('Warning: Graphite returned ' + str(error) + ' for ' + url)
                break

            box = (offset, 0, offset + settings.GRAPHITE_SPRITE_WIDTH,
                   settings.GRAPHITE_SPRITE_HEIGHT)
            spriteimg.paste(Image.open(tmpimg), box)
            offset += settings.GRAPHITE_SPRITE_WIDTH
            offset += settings.GRAPHITE_SPRITE_SPACING
        else:
            spriteimg.save(settings.GRAPHITE_SPRITE_PATH + '/' +
                           server['hostname'] + '.png')
