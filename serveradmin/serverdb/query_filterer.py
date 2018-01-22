from collections import defaultdict

from serveradmin.serverdb.models import (
    Attribute,
    Servertype,
    ServertypeAttribute,
    Server,
)
from serveradmin.serverdb.sql_generator import get_server_query


class QueryFilterer(object):
    def __init__(self, filters):
        # We can just deal with the servertype filter ourself.
        if 'servertype' in filters:
            servertype_filt = filters.pop('servertype')
        else:
            servertype_filt = None

        self._attribute_filters = []
        real_attributes = []
        for attribute_id, filt in filters.items():
            attribute = Attribute.objects.get(pk=attribute_id)
            self._attribute_filters.append((attribute, filt))
            if not attribute.special:
                real_attributes.append(attribute)

        self._possible_servertypes = _get_possible_servertypes(real_attributes)
        if servertype_filt:
            self._possible_servertypes = list(filter(
                lambda s: servertype_filt.matches(s.pk),
                self._possible_servertypes,
            ))

    def __iter__(self):
        # If there are no possible matches, there is no need to make
        # a database query.
        if self._possible_servertypes:
            result = Server.objects.raw(get_server_query(
                self._possible_servertypes, self._attribute_filters
            ))
        else:
            result = []

        return iter(result)


def _get_possible_servertypes(attributes):
    servertypes = set(Servertype.objects.all())

    if attributes:
        attribute_servertypes = defaultdict(set)
        for sa in ServertypeAttribute.query(attributes=attributes).all():
            attribute_servertypes[sa.attribute].add(sa.servertype)

        for new in attribute_servertypes.values():
            servertypes = servertypes.intersection(new)

    return servertypes
