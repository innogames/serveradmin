from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.iprange.views',
    url(r'^$', 'index', name='iprange_index'),
    url(r'^details/([\w\._-]+)$', 'details', name='iprange_details'),
)
