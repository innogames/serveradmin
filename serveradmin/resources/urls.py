from django.conf.urls import url

from serveradmin.resources.views import index, graph_popup

urlpatterns = [
    url(r'^$', index, name='resources_index'),
    url(r'^graph_popup$', graph_popup, name='resources_graph_popup'),
]
