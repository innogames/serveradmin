from typing import List

from django.conf import settings

from adminapi.filters import Not, Any
from .models import Domain
from ..dataset import Query


def get_settings(key: str) -> List:
    """Get PowerDNS domain settings

    Returns the PDNS.domain django settings or an empty list if not setup.
    :param key:
    """

    assert key in ['domain', 'record'], 'Unknown key for settings!'

    if settings.PDNS:
        return settings.PDNS.get(key, [])

    return list()


def get_domains_out_of_sync() -> Query:
    """Get domains not synchronised to PowerDNS

    Returns all serveradmin objects representing domains not synchronised to
    PowerDNS.

    :return:
    """
    in_sync = Domain.objects.all().values_list('id', flat=True)
    servertypes = [setting['servertype'] for setting in get_settings('domain')]

    return Query({
        'object_id': Not(Any(*in_sync)),
        'servertype': Any(*servertypes)
    })
