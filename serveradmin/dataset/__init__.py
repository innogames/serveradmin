from collections import defaultdict

from django.core.exceptions import ValidationError

from adminapi.dataset import BaseQuery, ServerObject
from adminapi.filters import BaseFilter
from serveradmin.serverdb.models import (   # TODO: Don't use the models at all
    Attribute, Server, Servertype, ServertypeAttribute
)
from serveradmin.serverdb.query_filterer import QueryFilterer
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)
from serveradmin.dataset.commit import commit_changes


class Query(BaseQuery):

    def new_object(self, servertype):
        server_obj = ServerObject(get_default_attribute_values(servertype))
        self.get_results().append(server_obj)

        return server_obj

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    def get_results(self):
        if self._results is None:
            servers = _filter_servers(self._filters)
            self._results = _materialize_servers(
                servers, self._restrict, self._order_by
            )
        return self._results


# XXX: Deprecated
def query(**kwargs):
    return Query(kwargs)


def _filter_servers(filters):
    attributes = []
    attribute_filters = {}
    servertypes = set(Servertype.objects.all())
    for attribute_id, filt in filters.items():
        assert isinstance(filt, BaseFilter)

        # We can just deal with the servertype filters ourself.
        if attribute_id == 'servertype':
            servertypes = {s for s in servertypes if filt.matches(s.pk)}
            continue

        try:
            attribute = Attribute.objects.get(pk=attribute_id)
        except Attribute.DoesNotExist:
            raise ValidationError(
                'Invalid attribute: {0}'.format(attribute_id)
            )

        attribute_filters[attribute] = filt

        if not attribute.special:
            attributes.append(attribute)

    if attributes:
        attribute_servertypes = defaultdict(set)
        for sa in ServertypeAttribute.query(attributes=attributes).all():
            attribute_servertypes[sa.attribute].add(sa.servertype)
        for new in attribute_servertypes.values():
            servertypes = servertypes.intersection(new)

    if not servertypes:
        return []

    return Server.objects.raw(
        QueryFilterer(servertypes, attribute_filters).build_sql()
    )


def _materialize_servers(servers, restrict, order_by=None):
    joins = {}
    if not restrict:
        # None means query everything to the materializer.
        attribute_ids = None
    else:
        attribute_ids = set(order_by or [])

        for item in restrict:
            if isinstance(item, dict):
                if len(item) != 1:
                    raise ValidationError('Malformatted join restriction')
                for attribute_id, value in item.items():
                    pass
                joins[attribute_id] = value
                attribute_ids.add(attribute_id)
            else:
                attribute_ids.add(item)
    server_ids = (s.server_id for s in servers)
    materializer = QueryMaterializer(servers, attribute_ids)
    if order_by:
        def order_by_key(key):
            return tuple(
                materializer.get_order_by_attribute(key, a)
                for a in order_by
            )

        server_ids = sorted(server_ids, key=order_by_key)

    join_results = _get_join_results(materializer, joins)
    return [
        ServerObject(materializer.get_attributes(i, join_results), i)
        for i in server_ids
    ]


def _get_join_results(materializer, joins):
    results = dict()
    for attribute_id, restrict in joins.items():
        servers = materializer.get_servers_to_join(attribute_id)
        results[attribute_id] = {
            s.object_id: s
            for s in _materialize_servers(servers, restrict)
        }
    return results
