"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

from adminapi.dataset import BaseQuery, DatasetObject
from serveradmin.serverdb.query_committer import commit_query
from serveradmin.serverdb.query_executer import execute_query
from serveradmin.serverdb.query_materializer import (
    get_default_attribute_values
)


class Query(BaseQuery):

    def _fetch_new_object(self, servertype):
        return DatasetObject(get_default_attribute_values(servertype))

    def commit(self, app=None, user=None):
        commit_obj = self._build_commit_object()
        commit_query(app=app, user=user, **commit_obj)
        self._confirm_changes()

    def _fetch_results(self):
        return execute_query(self._filters, self._restrict, self._order_by)
