from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.colo.views',
    url(r'^index$', 'index', name='colo_index'),
)
