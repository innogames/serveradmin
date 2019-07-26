"""Serveradmin - Remote HTTP API

Copyright (c) 2019 InnoGames GmbH
"""

from django.conf.urls import url

from serveradmin.api.views import (
    health_check,
    doc_functions,
    dataset_query,
    dataset_commit,
    dataset_new_object,
    dataset_create,
    api_call,
)

urlpatterns = [
    url('^health_check$', health_check),
    url('^functions$', doc_functions),
    url('^dataset/query$', dataset_query),
    url('^dataset/commit$', dataset_commit),
    url('^dataset/new_object$', dataset_new_object),
    url('^dataset/create$', dataset_create),
    url('^call$', api_call),
]
