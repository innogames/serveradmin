from itertools import chain
from typing import List, Dict

from django.conf import settings


class DomainSettings:
    def __init__(self):
        self.__settings = None

    def _settings(self) -> List[Dict]:
        if not self.__settings:
            self.__settings = settings.PDNS.get('domain')

        return self.__settings

    def get_servertypes(self) -> List:
        return [d['servertype'] for d in self._settings()]

    def get_attributes(self) -> List:
        return list(
            set(chain(*[d['attributes'].values() for d in self._settings()])))

    def get_settings(self, servertype: str) -> dict:
        return next(
            filter(lambda d: d['servertype'] == servertype, self._settings()))
