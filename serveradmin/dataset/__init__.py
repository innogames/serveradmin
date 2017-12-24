from adminapi.dataset import BaseQuery, DatasetObject
from serveradmin.serverdb.query_filterer import QueryFilterer
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)
from serveradmin.dataset.commit import commit_changes


class Query(BaseQuery):

    def new_object(self, servertype):
        obj = DatasetObject(get_default_attribute_values(servertype))
        self.get_results().append(obj)

        return obj

    def commit(self, *args, **kwargs):
        commit = self._build_commit_object()
        commit_changes(commit, *args, **kwargs)
        self._confirm_changes()

    def get_results(self):
        if self._results is None:
            filterer = QueryFilterer(self._filters)
            self._results = list(QueryMaterializer(
                filterer, self._restrict, self._order_by
            ))
        return self._results


# XXX: Deprecated
def query(**kwargs):
    return Query(kwargs)
