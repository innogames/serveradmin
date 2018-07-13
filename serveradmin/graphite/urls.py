"""Serveradmin - Graphite Integration

Copyright (c) 2018 InnoGames GmbH
"""

from django.conf.urls import url

from serveradmin.graphite.views import graph, graph_table

urlpatterns = [
    url(r'^graph_table$', graph_table, name='graphite_graph_table'),
    url(r'^graph', graph, name='graphite_graph'),
]
