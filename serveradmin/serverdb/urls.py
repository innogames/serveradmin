"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

from django.conf.urls import url

from serveradmin.serverdb.views import changes, restore_deleted, history

urlpatterns = [
    url(r'^changes$', changes, name='serverdb_changes'),
    url(
        r'^changes_restore/(\d+)$',
        restore_deleted,
        name='serverdb_restore_deleted',
    ),
    url(r'^history$', history, name='serverdb_history'),
]
