from serveradmin.api.decorators import api_view
from serveradmin.dataset.base import lookups
from serveradmin.dataset import QuerySet
from serveradmin.dataset.filters import filter_from_obj

@api_view
def echo(request, app, data):
    return data

@api_view
def dataset_query(request, app, data):
    if not all(x in data for x in ('filters', 'restrict', 'augmentations')):
        raise ValueError('Invalid query object')
    filters = {}
    for attr, filter_obj in data['filters'].iteritems():
        filters[attr] = filter_from_obj(filter_obj)
    q = QuerySet(filters=filters)
    if data['restrict']:
        q.restrict(*data['restrict'])
    if data['augmentations']:
        q.augment(*data['augmentations'])

    return {
        'status': 'success',
        'servers': q.get_raw_results(),
        'convert_set': [attr.name for attr in lookups.attr_ids.itervalues()
                        if attr.multi],
        'convert_ip': [attr.name for attr in lookups.attr_ids.itervalues()
                        if attr.type == 'ip']
    }

@api_view
def dataset_commit(request, app, data):
    pass
