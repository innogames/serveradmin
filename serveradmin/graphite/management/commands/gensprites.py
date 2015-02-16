import urllib2
from PIL import Image
from io import BytesIO

from django.core.management.base import NoArgsCommand
from django.core.cache import cache
from django.conf import settings

from serveradmin.graphite.models import GraphManager

class Command(NoArgsCommand):
    """Generate sprites from the overview graphics
    """

    help = __doc__
    sprite_path = settings.ROOT_DIR + '/graphite/static/graph_sprite'
    graph_width = 112
    graph_height = 45
    graph_spacing = 8
    manager = GraphManager()
    custom_params = 'width=112&height=45&graphOnly=true'

    def handle_noargs(self, **kwargs):
        """The entry point of the command
        """

        # Imports from serveradmin.dataset fail on initialization of commands.
        from serveradmin.dataset import query

        query_kwargs = {
            self.manager.overview_attrib_name: self.manager.overview_attrib_value,
        }
        for hw_host in query(**query_kwargs).restrict('hostname'):
            self.generate_sprite(hw_host['hostname'])

    def generate_sprite(self, hostname):
        """The main function
        """

        group = self.manager.overview_graph_group()
        table = group.graph_table(hostname, custom_params=self.custom_params)
        urls = [v2 for k1, v1 in table for k2, v2 in v1]
        sprite_width = (len(urls) * self.graph_width +
                        (len(urls) - 1) * self.graph_spacing)
        spriteimg = Image.new('RGB',
                              (sprite_width, self.graph_height), (255,) * 3)
        offset = 0

        for url in urls:
            opener = urllib2.build_opener()
            opener.addheaders.append(('Cookie',
                                      'sessionid=' + settings.GRAPHITE_COOKIE))
            tmpimg = BytesIO(opener.open(url).read())

            box = (offset, 0, offset + self.graph_width, self.graph_height)
            spriteimg.paste(Image.open(tmpimg), box)
            offset += 120

        spriteimg.save(self.sprite_path + '/' + hostname + '.png')
