from serveradmin.dataset.queryset import QuerySet


def query(**kwargs):
    return QuerySet(kwargs)
