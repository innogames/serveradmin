from django.conf.urls import url

from serveradmin.api.views import (
    doc_functions,
    dataset_query,
    dataset_commit,
    dataset_new_object,
    dataset_create,
    dataset_get_commits,
    api_call,
)

urlpatterns = [
    url('^functions$', doc_functions),
    url('^dataset/query$', dataset_query),
    url('^dataset/commit$', dataset_commit),
    url('^dataset/new_object$', dataset_new_object),
    url('^dataset/create$', dataset_create),
    url('^dataset/get_commits$', dataset_get_commits),
    url('^call$', api_call),
]
