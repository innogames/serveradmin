from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.dataset.views',
    url(r'^servertypes$', 'servertypes', name='dataset_servertypes'),
    url(r'^servertype/([\w\._-]+)$', 'view_servertype',
            name='dataset_view_servertype'),
)
