from serveradmin.api.decorators import api_view
from serveradmin.dataset.base import lookups
from serveradmin.dataset import QuerySet
from serveradmin.dataset.filters import filter_from_obj
from serveradmin.dataset.commit import commit_changes, CommitError

@api_view
def echo(request, app, data):
    return data

@api_view
def dataset_query(request, app, data):
    if not all(x in data for x in ('filters', 'restrict', 'augmentations')):
        return {
            'status': 'error',
            'type': 'ValueError',
            'message': 'Invalid query object'
        }
   
    try:
        filters = {}
        for attr, filter_obj in data['filters'].iteritems():
            filters[attr] = filter_from_obj(filter_obj)

        q = QuerySet(filters=filters)
        if data['restrict']:
            q.restrict(*data['restrict'])
        if data['augmentations']:
            q.augment(*data['augmentations'])
    except ValueError, e:
        return {
            'status': 'error',
            'type': 'ValueError',
            'message': e.message
        }

    attributes = {}
    for attr in lookups.attr_ids.itervalues():
        attributes[attr.name] = {
            'multi': attr.multi,
            'type': attr.type
        }

    return {
        'status': 'success',
        'servers': q.get_raw_results(),
        'attributes': attributes
    }

@api_view
def dataset_commit(request, app, data):
    try:
        if 'changes' not in data or 'deleted' not in data:
            raise ValueError('Invalid changes')

        # Convert keys back to integers (json doesn't handle integer keys)
        changes = {}
        for server_id, change in data['changes'].iteritems():
            changes[int(server_id)] = change

        commit = {'deleted': data['deleted'], 'changes': changes}
        commit_changes(commit)
        return {
            'status': 'success'
        }
    except (ValueError, CommitError), e:
        return {
            'status': 'error',
            'type': e.__class__.__name__,
            'message': e.message
        }
