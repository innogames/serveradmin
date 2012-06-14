from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.api.views',
    url(r'^list_functions', 'list_functions', name='api_list_functions'),
    url(r'^echo$', 'echo', name='api_echo'),
    url(r'^dataset/query$', 'dataset_query', name='api_dataset_query'),
    url(r'^dataset/commit$', 'dataset_commit', name='api_dataset_commit'),
    url(r'^dataset/create$', 'dataset_create', name='api_dataset_create'),
    url(r'^call', 'api_call', name='api_call'),
)
