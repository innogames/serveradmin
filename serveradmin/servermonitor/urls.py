from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.servermonitor.views',
    url(r'^$', 'index', name='servermonitor_index'),
    url(r'^graph_table$', 'graph_table', name='servermonitor_graph_table'),
    url(r'^compare$', 'compare', name='servermonitor_compare'),
    url(r'^graph_popup$', 'graph_popup', name='servermonitor_graph_popup'),
    url(r'^livegraph$', 'livegraph', name='servermonitor_livegraph'),
    url(r'^livegraph/data$', 'livegraph_data',
            name='servermonitor_livegraph_data'),
    url(r'^reload$', 'reload', name='servermonitor_reload'),
)
