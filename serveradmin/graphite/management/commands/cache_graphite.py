"""Serveradmin - Graphite Integration

Copyright (c) 2023 InnoGames GmbH
"""

import json
import time
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from os import mkdir
from os.path import isdir
from urllib.error import HTTPError
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    build_opener
)

from PIL import Image
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from adminapi import filters
from serveradmin.dataset import Query
from serveradmin.graphite.models import (
    GRAPHITE_ATTRIBUTE_ID,
    Collection,
    AttributeFormatter,
)
from serveradmin.serverdb.models import Server


class Command(BaseCommand):
    """Generate sprites and update numeric values for collections."""
    help = __doc__

    def handle(self, *args, **kwargs):
        """The entry point of the command"""

        start = time.time()

        sprite_params = settings.GRAPHITE_SPRITE_PARAMS
        sprite_dir = settings.MEDIA_ROOT + '/graph_sprite'
        if not isdir(sprite_dir):
            mkdir(sprite_dir)

        # We will make sure to generate a single sprite for a single hostname.
        for collection in Collection.objects.filter(overview=True):
            collection_start = time.time()

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

            collection_duration = time.time() - collection_start
            print('[{}] Collection {} finished after {} seconds'.format(
                datetime.now(), collection.name, collection_duration))

        duration = time.time() - start
        print('[{}] Finished after {} seconds'.format(datetime.now(),
                                                      duration))

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
                # Lock server for changes to avoid nonrepeatable reads in the
                # query_committer.
                locked_server = Server.objects.select_for_update().get(
                    server_id=server.object_id)
                locked_server.servernumberattribute_set.update_or_create(
                    server_id=locked_server.server_id,
                    attribute=numeric.attribute,
                    defaults={'value': Decimal(value)},
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
