from serveradmin.dataset.queryset import Query


# XXX Deprecated
def query(**kwargs):
    return Query(kwargs)
