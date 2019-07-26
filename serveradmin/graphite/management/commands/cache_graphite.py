"""Serveradmin - Graphite Integration

Copyright (c) 2019 InnoGames GmbH
"""

import json
from os import mkdir
from os.path import isdir
import time
from PIL import Image
from io import BytesIO
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener
)
from urllib.error import HTTPError

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from serveradmin.dataset import Query
from serveradmin.graphite.models import (
    GRAPHITE_ATTRIBUTE_ID,
    Collection,
    AttributeFormatter,
)
from serveradmin.serverdb.models import ServerNumberAttribute
from adminapi import filters


class Command(BaseCommand):
    """Generate sprites from the overview graphics"""
    help = __doc__

    def handle(self, *args, **kwargs):
        """The entry point of the command"""
        sprite_params = settings.GRAPHITE_SPRITE_PARAMS
        sprite_dir = settings.MEDIA_ROOT + '/graph_sprite'
        if not isdir(sprite_dir):
            mkdir(sprite_dir)

        # We will make sure to generate a single sprite for a single hostname.
        for collection in Collection.objects.filter(overview=True):
            collection_dir = sprite_dir + '/' + collection.name
            if not isdir(collection_dir):
                mkdir(collection_dir)

            for server in Query(
                {
                    GRAPHITE_ATTRIBUTE_ID: collection.name,
                    'state': filters.Not('retired'),
                }):
                graph_table = collection.graph_table(server, sprite_params)
                if graph_table:
                    self.generate_sprite(collection_dir, graph_table, server)
                self.cache_numerics(collection, server)

    def generate_sprite(self, collection_dir, graph_table, server):
        """Generate sprites for the given server using the given collection"""
        graphs = [v2 for k1, v1 in graph_table for k2, v2 in v1]
        sprite_width = settings.GRAPHITE_SPRITE_WIDTH
        sprite_height = settings.GRAPHITE_SPRITE_HEIGHT
        total_width = len(graphs) * sprite_width
        sprite_img = Image.new('RGB', (total_width, sprite_height), (255,) * 3)

        for graph, offset in zip(graphs, range(0, total_width, sprite_width)):
            response = self.get_from_graphite(graph)
            if response:
                box = (offset, 0, offset + sprite_width, sprite_height)
                sprite_img.paste(Image.open(BytesIO(response)), box)

        sprite_img.save(collection_dir + '/' + server['hostname'] + '.png')

    def cache_numerics(self, collection, server):
        """Generate sprites for the given server using the given collection"""
        for numeric in collection.numeric_set.all():
            formatter = AttributeFormatter()
            params = formatter.vformat(numeric.params, (), server)
            response = self.get_from_graphite(params)
            if not response:
                continue

            response_json = json.loads(response.decode('utf8'))
            try:
                value = response_json[0]['datapoints'][0][0]
            except IndexError:
                print(
                    (
                        "Warning: Graphite response '{}' for collection {}/{}"
                        " on server {} couldn't be parsed"
                    ).format(response, collection, numeric, server['hostname'])
                )
                continue

            if value is None:
                continue

            # Django can be set up to implicitly execute commands in database
            # transactions.  We don't want that behavior in here even when
            # it is set up like this.  This process takes a long time.
            # We want the values to be immediately available to the users.
            with transaction.atomic():
                ServerNumberAttribute.objects.update_or_create(
                    server_id=server.object_id,
                    attribute=numeric.attribute,
                    defaults={'value': value},
                )

    def get_from_graphite(self, params):
        """Make a GET request to Graphite with the given params"""
        password_mgr = HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(
            None,
            settings.GRAPHITE_URL,
            settings.GRAPHITE_USER,
            settings.GRAPHITE_PASSWORD,
        )
        auth_handler = HTTPBasicAuthHandler(password_mgr)
        url = '{0}/render?{1}'.format(
            settings.GRAPHITE_URL, params
        )
        start = time.time()

        try:
            with build_opener(auth_handler).open(url) as response:
                return response.read()
        except HTTPError as error:
            print('Warning: Graphite returned ' + str(error) + ' to ' + url)
        finally:
            end = time.time()
            if end - start > 10:
                print(
                    'Warning: Graphite request to {0} took {1} seconds'.format(
                        url, end - start
                    )
                )
