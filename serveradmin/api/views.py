import json

from adminapi.utils.json import json_encode_extra 

from serveradmin.api import ApiError, AVAILABLE_API_FUNCTIONS
from serveradmin.api.decorators import api_view
from serveradmin.dataset.base import lookups
from serveradmin.dataset import QuerySet
from serveradmin.dataset.filters import filter_from_obj
from serveradmin.dataset.commit import commit_changes, CommitError
from serveradmin.dataset.cache import QuerysetCacher

class StringEncoder(object):
    def loads(self, x):
        return x

    def dumps(self, x):
        return x

    def load(self, file):
        return file.read()

    def dump(self, val, file):
        return file.write(val)

@api_view
def echo(request, app, data):
    return data

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

        q = QuerySet(filters=filters, for_export=True)
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

    def _build_response(server_data):
        attributes = {}
        for attr in lookups.attr_ids.itervalues():
            attributes[attr.name] = {
                'multi': attr.multi,
                'type': attr.type
            }
        
        return json.dumps({
            'status': 'success',
            'servers': q.get_raw_results(),
            'attributes': attributes
        }, default=json_encode_extra)

    cacher = QuerysetCacher(q, 'api', encoder=StringEncoder(),
            post_fetch=_build_response)
    return cacher.get_results()
dataset_query.encode_json = False
dataset_query = api_view(dataset_query)

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

@api_view
def api_call(request, app, data):
    try:
        if not all(x in data for x in ('group', 'name', 'args', 'kwargs')):
            raise ValueError('Invalid API call')
        
        try:
            fn = AVAILABLE_API_FUNCTIONS[data['group']][data['name']]
        except KeyError:
            raise ValueError('No such function')

        retval = fn(*data['args'], **data['kwargs'])
        print 'retval', retval
        return {
            'status': 'success',
            'retval': retval
        }

    except (ValueError, TypeError, ApiError), e:
        return {
            'status': 'error',
            'type': e.__class__.__name__,
            'message': e.message
        }
