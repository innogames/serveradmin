import os
from operator import itemgetter
try:
    import simplejson as json
except ImportError:
    import json

from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admindocs.utils import trim_docstring, parse_docstring
from django.conf import settings

from adminapi.utils.json import json_encode_extra 

from serveradmin.api import ApiError, AVAILABLE_API_FUNCTIONS
from serveradmin.api.decorators import api_view
from serveradmin.api.utils import build_function_description
from serveradmin.dataset.base import lookups
from serveradmin.dataset import QuerySet
from serveradmin.dataset.filters import filter_from_obj, ExactMatch
from serveradmin.dataset.commit import commit_changes, CommitError
from serveradmin.dataset.create import create_server
from serveradmin.dataset.cache import QuerysetCacher

@login_required
def documentation(request):
    return TemplateResponse(request, 'api/documentation.html')

@login_required
def doc_pythonapi(request):
    docfile = os.path.join(settings.DOCUMENTATION_DATADIR, 'python-api.fjson')
    with open(docfile) as f:
        document = json.load(f)
    return TemplateResponse(request, 'api/documentation_page.html', {
        'document': document
    })

@login_required
def doc_functions(request):
    group_list = []
    for group_name, functions in AVAILABLE_API_FUNCTIONS.iteritems():
        function_list = []
        for name, function in functions.iteritems():
            heading, body, metadata = parse_docstring(function.__doc__)
            body = trim_docstring(body)
            function_list.append({
                'name': name,
                'description': build_function_description(function),
                'docstring': trim_docstring('{0}\n\n{1}'.format(heading, body))
            })
        function_list.sort(key=itemgetter('name'))
            
        group_list.append({
            'name': group_name,
            'function_list': function_list
        })
    group_list.sort(key=itemgetter('name'))
    return TemplateResponse(request, 'api/list_functions.html', {
        'group_list': group_list
    })

@api_view
def echo(request, app, data):
    return data

#@api_view decorator is used after setting an attribute on this function
def dataset_query(request, app, data):
    class StringEncoder(object):
        def loads(self, x):
            return x

        def dumps(self, x):
            return x

        def load(self, file):
            return file.read()

        def dump(self, val, file):
            return file.write(val)
    
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
        return json.dumps({
            'status': 'success',
            'servers': q.get_raw_results(),
            'attributes': _build_attributes()
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
def dataset_create(request, app, data):
    try:
        required = ['attributes', 'skip_validation', 'fill_defaults',
                'fill_defaults_all']
        if not all(key in data for key in required):
            raise ValueError('Invalid create request')
        if not isinstance(data['attributes'], dict):
            raise ValueError('Attributes must be a dictionary')

        create_server(data['attributes'], data['skip_validation'],
            data['fill_defaults'], data['fill_defaults_all'])
        return {
            'status': 'success',
            'attributes': _build_attributes(),
            'servers': QuerySet(filters={'hostname': ExactMatch(
                data['attributes']['hostname'])}).get_raw_results()
        }
    except (ValueError, CommitError), e:
        return {
            'status': 'error',
            'type': e.__class__.__name__,
            'message': e.message
        }

def _build_attributes():
    attributes = {}
    for attr in lookups.attr_ids.itervalues():
        attributes[attr.name] = {
            'multi': attr.multi,
            'type': attr.type
        }
    return attributes

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
