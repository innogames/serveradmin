from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.resources.views',
    url(r'^$', 'index', name='resources_index'),
    url(r'^graph_popup$', 'graph_popup', name='resources_graph_popup'),
    url(r'^projects$', 'projects', name='resources_projects'),
)
