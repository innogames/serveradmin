from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.servermonitor.views',
    url(r'^graph_table/([\w\._-]+)$', 'graph_table',
        name='servermonitor_graph_table'),
)
