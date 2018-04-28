from adminapi.dataset import BaseQuery, DatasetObject
from serveradmin.serverdb.query_committer import QueryCommitter
from serveradmin.serverdb.query_filterer import QueryFilterer
from serveradmin.serverdb.query_materializer import (
    QueryMaterializer,
    get_default_attribute_values,
)


class Query(BaseQuery):

    def _fetch_new_object(self, servertype):
        return DatasetObject(get_default_attribute_values(servertype))

    def commit(self, app=None, user=None):
        commit = self._build_commit_object()
        QueryCommitter(app=app, user=user, **commit)()
        self._confirm_changes()

    def _fetch_results(self):
        filterer = QueryFilterer(self._filters)
        return QueryMaterializer(filterer, self._restrict, self._order_by)


# XXX: Deprecated
def query(**kwargs):
    return Query(kwargs, None)
