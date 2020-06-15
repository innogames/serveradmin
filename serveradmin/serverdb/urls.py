"""Serveradmin

Copyright (c) 2020 InnoGames GmbH
"""

from django.urls import path

from serveradmin.serverdb.views import changes, restore_deleted, history

urlpatterns = [
    path('changes', changes, name='serverdb_changes'),
    path('changes_restore/<int:change_commit_id>', restore_deleted,
         name='serverdb_restore_deleted'),
    path('history', history, name='serverdb_history'),
]
