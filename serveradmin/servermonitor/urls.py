from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.servermonitor.views',
    url(r'^$', 'index', name='servermonitor_index'),
    url(r'^graph_table$', 'graph_table', name='servermonitor_graph_table'),
    url(r'^compare$', 'compare', name='servermonitor_compare'),
    url(r'^graph_popup$', 'graph_popup', name='servermonitor_graph_popup'),
    url(r'^reload$', 'reload', name='servermonitor_reload'),
)
