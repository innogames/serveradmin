"""Serveradmin

Copyright (c) 2022 InnoGames GmbH
"""

from django.urls import path

from serveradmin.serverdb.views import changes, recreate, history

urlpatterns = [
    path('changes', changes, name='serverdb_changes'),
    path('recreate/<int:change_id>', recreate, name='serverdb_recreate'),
    path('history', history, name='serverdb_history'),
]
