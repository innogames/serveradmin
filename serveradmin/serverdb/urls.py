"""Serveradmin

Copyright (c) 2022 InnoGames GmbH
"""

from django.urls import path

from serveradmin.serverdb.views import changes, restore, history

urlpatterns = [
    path('changes', changes, name='serverdb_changes'),
    path('restore/<int:change_id>', restore, name='serverdb_restore'),
    path('history', history, name='serverdb_history'),
]
