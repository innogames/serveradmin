from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.api.views',
    url(r'^documentation$', 'documentation', name='api_doc_index'),
    url(r'^documentation/api_functions$', 'doc_functions', name='api_doc_functions'),
    url(r'^documentation/python_api$', 'doc_pythonapi', name='api_doc_pythonapi'),
    url(r'^echo$', 'echo', name='api_echo'),
    url(r'^dataset/query$', 'dataset_query', name='api_dataset_query'),
    url(r'^dataset/commit$', 'dataset_commit', name='api_dataset_commit'),
    url(r'^dataset/create$', 'dataset_create', name='api_dataset_create'),
    url(r'^call', 'api_call', name='api_call'),
)
