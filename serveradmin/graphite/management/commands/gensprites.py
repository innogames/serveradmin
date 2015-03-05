import urllib2
from PIL import Image
from io import BytesIO

from django.core.management.base import NoArgsCommand
from django.core.cache import cache
from django.conf import settings

from serveradmin.graphite.models import GraphGroup

class Command(NoArgsCommand):
    """Generate sprites from the overview graphics
    """

    help = __doc__
    sprite_path = settings.MEDIA_ROOT + '/graph_sprite'
    graph_width = 112
    graph_height = 45
    graph_spacing = 8
    custom_params = 'width=112&height=45&graphOnly=true'

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

        table = graph_group.graph_table(server, custom_params=self.custom_params)
        graphs = [v2 for k1, v1 in table for k2, v2 in v1]
        sprite_width = (len(graphs) * self.graph_width +
                        (len(graphs) - 1) * self.graph_spacing)
        spriteimg = Image.new('RGB',
                              (sprite_width, self.graph_height), (255,) * 3)
        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie',
                                  'sessionid=' + settings.GRAPHITE_COOKIE))
        offset = 0

        for graph in graphs:
            url = settings.GRAPHITE_URL + '/render?' + graph

            try:
                tmpimg = BytesIO(opener.open(url).read())
            except urllib2.HTTPError:
                print('Warning: Graphite returned error for ' + url)
                break

            box = (offset, 0, offset + self.graph_width, self.graph_height)
            spriteimg.paste(Image.open(tmpimg), box)
            offset += self.graph_width + self.graph_spacing
        else:
            spriteimg.save(self.sprite_path + '/' + server['hostname'] + '.png')
