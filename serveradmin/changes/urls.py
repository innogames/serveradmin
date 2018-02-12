from django.conf.urls import url

from serveradmin.changes.views import commits, history, restore_deleted

urlpatterns = [
    url(r'^changes$', commits, name='changes_commits'),
    url(
        r'^changes_restore/(\d+)$',
        restore_deleted,
        name='serverdb_restore_deleted',
    ),
    url(r'^history$', history, name='changes_history'),
]
