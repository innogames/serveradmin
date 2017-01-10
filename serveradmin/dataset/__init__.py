from serveradmin.dataset.queryset import QuerySet
from serveradmin.dataset.filters import _prepare_filter


def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.items())
    return QuerySet(filters)
