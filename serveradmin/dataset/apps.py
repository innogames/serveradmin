from django.apps import AppConfig
from django.core.signals import request_started

from serveradmin.database.base import _read_lookups

class DatasetConfig(AppConfig):
    name = 'dataset'
    def ready(self):
        _read_lookups()
        request_started.connect(_read_lookups)
