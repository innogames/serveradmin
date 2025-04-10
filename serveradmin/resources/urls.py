"""Serveradmin - Graphite Integration

Copyright (c) 2020 InnoGames GmbH
"""

from django.urls import path

from serveradmin.resources.views import graph_popup, index

urlpatterns = [
    path('', index, name='resources_index'),
    path('graph_popup', graph_popup, name='resources_graph_popup'),
]
