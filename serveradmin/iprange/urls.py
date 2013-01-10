from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.iprange.views',
    url(r'^$', 'index', name='iprange_index'),
    url(r'^add$', 'add', name='iprange_add'),
    url(r'^edit/([\w\._-]+)$', 'edit', name='iprange_edit'),
    url(r'^delete/([\w\._-]+)$', 'delete', name='iprange_delete'),
    url(r'^details/([\w\._-]+)$', 'details', name='iprange_details'),
    url(r'^routes/([\w\._-]+)$', 'routes', name='iprange_routes'),
    url(r'^routes/([\w\._-]+)/add$', 'routes_add', name='iprange_routes_add'),
    url(r'^routes/delete/(\d+)$', 'routes_del', name='iprange_routes_del'),
)
