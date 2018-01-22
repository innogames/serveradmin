from adminapi.dataset import BaseQuery, DatasetObject
from serveradmin.serverdb.query_committer import QueryCommitter
from serveradmin.serverdb.query_filterer import QueryFilterer
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)


class Query(BaseQuery):

    def new_object(self, servertype):
        obj = DatasetObject(get_default_attribute_values(servertype))
        self.get_results().append(obj)

        return obj

    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        QueryCommitter(app=app, user=user, **commit)()
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
