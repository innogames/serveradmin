"""Serveradmin - Remote HTTP API

Copyright (c) 2020 InnoGames GmbH
"""

from django.urls import path

from serveradmin.api.views import (
    health_check,
    dataset_query,
    dataset_commit,
    dataset_new_object,
    dataset_create,
    api_call,
)

urlpatterns = [
    path('health_check', health_check),
    path('dataset/query', dataset_query),
    path('dataset/commit', dataset_commit),
    path('dataset/new_object', dataset_new_object),
    path('dataset/create', dataset_create),
    path('call', api_call),
]
