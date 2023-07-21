"""Serveradmin - Graphite Integration

Copyright (c) 2023 InnoGames GmbH
"""

import json
import time
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
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils.timezone import now

from adminapi import filters
from adminapi.parse import parse_query
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

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--collections", nargs='*', type=str, help='Generate/update only these collections.')
        parser.add_argument("--query", type=str, help="Generate/update only objects matching this Serveradmin query.")

    def handle(self, *args, **options):
        """The entry point of the command"""

        sprite_params = settings.GRAPHITE_SPRITE_PARAMS
        sprite_dir = settings.MEDIA_ROOT + '/graph_sprite'
        if not isdir(sprite_dir):
            mkdir(sprite_dir)

        collections = Collection.objects.filter(overview=True)
        if options['collections']:
            collections = collections.filter(name__in=options['collections'])

        for collection in collections:
            self.stdout.write(f"[{now()}] Starting collection {collection}")

            collection_dir = sprite_dir + '/' + collection.name
            if not isdir(collection_dir):
                mkdir(collection_dir)

            query_filter = {
                GRAPHITE_ATTRIBUTE_ID: collection.name,
                "state": filters.Not("retired"),
            }

            if options["query"]:
                query_filter.update(**parse_query(options["query"]))

            for server in Query(query_filter, ["hostname"]):
                graph_table = collection.graph_table(server, sprite_params)
                if graph_table:
                    self.generate_sprite(collection_dir, graph_table, server)
                    self.stdout.write(f"[{now()}] Generated sprite for {server['hostname']}")
                self.cache_numerics(collection, server)
                self.stdout.write(f"[{now()}] Updated numerics for {server['hostname']}")

            self.stdout.write(f"[{now()}] Finished collection {collection}")

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
                self.stdout.write(self.style.NOTICE(f"[{now()}] {server['hostname']}: Can't parse response {response} for {params}."))
                continue

            if value is None:
                self.stdout.write(self.style.NOTICE(f"[{now()}] {server['hostname']}: None value for {params} received."))
                continue

            # Django can be set up to implicitly execute commands in database
            # transactions.  We don't want that behavior in here even when
            # it is set up like this.  This process takes a long time.
            # We want the values to be immediately available to the users.
            with transaction.atomic():
                try:
                    # Lock server for changes to avoid non-repeatable reads in the
                    # query_committer.
                    locked_server = Server.objects.select_for_update().get(server_id=server.object_id)
                except Server.DoesNotExist:
                    self.stdout.write(self.style.NOTICE(f"[{now()}] {server['hostname']} has been deleted."))
                    continue

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
            self.stdout.write(self.style.NOTICE(f"Graphite returned {error} for {url}"))
        finally:
            end = time.time()
            if end - start > 10:
                self.stdout.write(self.style.WARNING(f"Graphite request {url} took {end - start} seconds"))
