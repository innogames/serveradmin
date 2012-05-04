from serveradmin.api.decorators import api_view
from serveradmin.dataset import query

@api_view
def echo(request, app, data):
    return data

@api_view
def dataset_query(request, app, data):
    # FIXME: Replace dummy with real action
    q = query(hostname='techerror.support')
    return {
        'success': True,
        'servers': q.get_raw_results(),
        'convert_set': [attr.name for attr in q.get_attr_lookup().itervalues()]
    }

@api_view
def dataset_commit(request, app, data):
    pass
