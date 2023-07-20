"""Serveradmin - Nessus Integration

Copyright (c) 2023 InnoGames GmbH
"""

from django.urls import path
from serveradmin.nessus.views import nessus_config

urlpatterns = [
    path("nessus_config", nessus_config, name="nessus_config"),
]
