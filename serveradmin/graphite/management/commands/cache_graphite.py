import urllib2, json, time
from PIL import Image
from io import BytesIO

from django.core.management.base import NoArgsCommand
from django.core.cache import cache
from django.conf import settings

import django_urlauth.utils
from serveradmin.graphite.models import Collection, NumericCache, AttributeFormatter

class Command(NoArgsCommand):
    """Generate sprites from the overview graphics
    """

    help = __doc__

    def handle_noargs(self, **kwargs):
        """The entry point of the command
        """

        # We will make sure to generate a single sprite for a single hostname.
        done_servers = set()
        for collection in Collection.objects.filter(overview=True):
            for server in collection.query():
                if server not in done_servers:
                    self.generate_sprite(collection, server)
                    self.cache_numeric_values(collection, server)
                    done_servers.add(server)

    def generate_sprite(self, collection, server):
        """Generates sprites for the given server using the given collection
        """

        table = collection.graph_table(server,
                                custom_params=settings.GRAPHITE_SPRITE_PARAMS)
        graphs = [v2 for k1, v1 in table for k2, v2 in v1]
        sprite_width = (len(graphs) * settings.GRAPHITE_SPRITE_WIDTH +
                        (len(graphs) - 1) * settings.GRAPHITE_SPRITE_SPACING)
        spriteimg = Image.new('RGB', (sprite_width,
                                      settings.GRAPHITE_SPRITE_HEIGHT),
                                      (255,) * 3)
        offset = 0

        for graph in graphs:
            response = self.get_from_graphite(graph)
            if response:
                box = (offset, 0, offset + settings.GRAPHITE_SPRITE_WIDTH,
                       settings.GRAPHITE_SPRITE_HEIGHT)
                spriteimg.paste(Image.open(BytesIO(response)), box)

            offset += settings.GRAPHITE_SPRITE_WIDTH
            offset += settings.GRAPHITE_SPRITE_SPACING

        spriteimg.save(settings.GRAPHITE_SPRITE_PATH + '/' +
                       server['hostname'] + '.png')


    def cache_numeric_values(self, collection, server):
        """Generates sprites for the given server using the given collection
        """

        for template in collection.template_set.filter(numeric_value=True):
            formatter = AttributeFormatter()
            params = formatter.vformat(template.params, (), server)
            response = self.get_from_graphite(params)
            if response:
                try:
                    value = json.loads(response)[0]['datapoints'][0][0]
                except IndexError:
                    print('Warning: Graphite response couldn\'t be parsed ' + response)
                else:
                    numeric_cache = NumericCache.objects.get_or_create(
                        template=template,
                        hostname=server['hostname'],
                    )[0]
                    numeric_cache.value = value
                    numeric_cache.save()

    def get_from_graphite(self, params):
        """Make a GET request to Graphite with the given params
        """

        token = django_urlauth.utils.new_token('serveradmin', settings.GRAPHITE_SECRET)
        url = settings.GRAPHITE_URL + '/render?__auth_token=' + token + '&' + params

        opener = urllib2.build_opener()
        start = time.time()
        try:
            return opener.open(url).read()
        except urllib2.HTTPError as error:
            print('Warning: Graphite returned ' + str(error) + ' to ' + url)
        finally:
            end = time.time()
            if end - start > 10:
                print('Warning: Graphite request took ' + str(end - start) + ' seconds to ' + url)
