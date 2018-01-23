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
        self._get_results().append(obj)

        return obj

    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        QueryCommitter(app=app, user=user, **commit)()
        self._confirm_changes()

    def _fetch_results(self):
        filterer = QueryFilterer(self._filters)
        return QueryMaterializer(filterer, self._restrict, self._order_by)


# XXX: Deprecated
def query(**kwargs):
    return Query(kwargs)
