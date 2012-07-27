from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.servermonitor.views',
    url(r'^$', 'index', name='servermonitor_index'),
    url(r'^graph_table/([\w\._-]+)$', 'graph_table',
        name='servermonitor_graph_table'),
    url(r'^compare$', 'compare', name='servermonitor_compare'),
    url(r'^reload$', 'reload', name='servermonitor_reload'),
)
