from serveradmin.dataset.queryset import QuerySet
from serveradmin.dataset.filters import _prepare_filter
from serveradmin.dataset.create import create_server

def query(**kwargs):
    filters = dict((k, _prepare_filter(v)) for k, v in kwargs.iteritems())
    return QuerySet(filters)

def create(attributes, skip_validation=False, fill_defaults=True,
        fill_defaults_all=False):
    server_id = create_server(attributes, skip_validation, fill_defaults,
            fill_defaults_all)
    return query(object_id=server_id).get()
