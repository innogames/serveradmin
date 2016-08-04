from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.serverdb.views',
    url(r'^changes$', 'changes', name='serverdb_changes'),
    url(
        r'^changes_restore/(\d+)$',
        'restore_deleted',
        name='serverdb_restore_deleted',
    ),
    url(r'^history$', 'history', name='serverdb_history'),
)
