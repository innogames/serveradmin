from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.api.views',
    url(r'^echo$', 'echo', name='api_echo'),
    url(r'^dataset/query$', 'dataset_query', name='api_dataset_query'),
)
