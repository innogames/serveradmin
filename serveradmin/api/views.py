"""Serveradmin - Remote HTTP API

Copyright (c) 2019 InnoGames GmbH
"""

from operator import itemgetter

from django.core.exceptions import (
    SuspiciousOperation,
    PermissionDenied,
    ValidationError,
)
from django.contrib.auth.decorators import login_required
from django.contrib.admindocs.utils import trim_docstring, parse_docstring
from django.template.response import TemplateResponse, HttpResponse

from adminapi.filters import FilterValueError, filter_from_obj
from serveradmin.api import ApiError, AVAILABLE_API_FUNCTIONS
from serveradmin.api.decorators import api_view
from serveradmin.api.utils import build_function_description
from serveradmin.serverdb.query_committer import commit_query
from serveradmin.serverdb.query_executer import execute_query
from serveradmin.serverdb.query_materializer import (
    get_default_attribute_values
)


class StringEncoder(object):
    def loads(self, x):
        return x

    def dumps(self, x):
        return x

    def load(self, file):
        return file.read()

    def dump(self, val, file):
        return file.write(val)


def health_check(request):
    """Check to determin if node is healthy

    This view is used by testtool and therefore mustn't require authentication
    to work. Unhealthy nodes will not be used to server requests.
    """
    return HttpResponse(status=242)


@api_view
def dataset_query(request, app, data):
    try:
        if 'filters' not in data or not isinstance(data['filters'], dict):
            raise SuspiciousOperation('Filters must be a dictionary')
        filters = {}
        for attr, filter_obj in data['filters'].items():
            filters[attr] = filter_from_obj(filter_obj)

        # Empty list means query all attributes to the older versions of
        # the adminapi.
        if not data.get('restrict'):
            restrict = None
        else:
            restrict = data['restrict']

        order_by = data.get('order_by')

        return {
            'status': 'success',
            'result': execute_query(filters, restrict, order_by),
        }
    except (FilterValueError, ValidationError) as error:
        return {
            'status': 'error',
            'type': 'ValueError',
            'message': str(error),
        }


@api_view
def dataset_new_object(request, app, data):
    try:
        servertype = request.GET['servertype']
    except KeyError as error:
        raise SuspiciousOperation(error)

    return {'result': get_default_attribute_values(servertype)}


@api_view
def dataset_commit(request, app, data):
    if not isinstance(data, dict):
        raise SuspiciousOperation('Invalid payload')

    # For backwards compatibility
    if 'changes' in data:
        data['changed'] = list(data['changes'].values())
        # Convert keys back to integers (json doesn't handle integer keys)
        for object_id, change in data['changes'].items():
            change['object_id'] = int(object_id)

    kwargs = {}
    for key, value in data.items():
        validate_func = globals().get('_validate_commit_' + key)
        if validate_func:
            if not isinstance(value, list):
                raise SuspiciousOperation('Invalid commit {}'.format(key))
            for item in value:
                validate_func(item)
            kwargs[key] = value

    try:
        commit_query(app=app, **kwargs)
    except ValidationError as error:
        return {
            'status': 'error',
            'type': error.__class__.__name__,
            'message': str(error),
        }

    return {
        'status': 'success',
    }


def _validate_commit_created(created):
    if not isinstance(created, dict):
        raise SuspiciousOperation('Invalid commit created')


def _validate_commit_changed(changes):
    if not isinstance(changes, dict):
        raise SuspiciousOperation('Invalid commit changes')

    for attribute_id, change in changes.items():
        if attribute_id == 'object_id':
            object_id_found = True
            continue

        if not isinstance(change, dict) or 'action' not in change:
            raise SuspiciousOperation(
                'Invalid commit changed for attribute "{}"'
                .format(attribute_id)
            )

        func = globals()['_validate_commit_changed_' + change['action']]
        func(change)

    if not object_id_found:
        raise SuspiciousOperation('Commit changed without object_id')


def _validate_commit_changed_update(change):
    if not all(x in change for x in ('old', 'new')):
        raise SuspiciousOperation('Invalid update change')


def _validate_commit_changed_new(change):
    if 'new' not in change:
        raise SuspiciousOperation('Invalid new change')


def _validate_commit_changed_delete(change):
    if 'old' not in change:
        raise SuspiciousOperation('Invalid delete change')


def _validate_commit_changed_multi(change):
    if not all(x in change for x in ('add', 'remove')):
        raise SuspiciousOperation('Invalid multi change')


def _validate_commit_deleted(deleted):
    if not isinstance(deleted, int):
        raise SuspiciousOperation(
            'Invalid commit deleted "{}"'.format(deleted)
        )


# XXX: Deprecated
@api_view
def dataset_create(request, app, data):
    required = [
        'attributes',
    ]
    if not all(key in data for key in required):
        raise SuspiciousOperation('Invalid create request')
    if not isinstance(data['attributes'], dict):
        raise SuspiciousOperation('Attributes must be a dictionary')

    try:
        commit_obj = commit_query([data['attributes']], app=app)
    except ValidationError as error:
        return {
            'status': 'error',
            'type': error.__class__.__name__,
            'message': str(error),
        }

    return {
        'status': 'success',
        'result': commit_obj.created,
    }


@api_view
def api_call(request, app, data):
    try:
        if not all(x in data for x in ('group', 'name', 'args', 'kwargs')):
            raise SuspiciousOperation('Invalid API call')

        allowed_methods = app.allowed_methods.splitlines()
        method_name = '{0}.{1}'.format(data['group'], data['name'])
        if not app.superuser and method_name not in allowed_methods:
            raise PermissionDenied(
                'Method {0} not allowed'.format(method_name)
            )

        try:
            fn = AVAILABLE_API_FUNCTIONS[data['group']][data['name']]
        except KeyError:
            raise ApiError('No such function')

        retval = fn(*data['args'], **data['kwargs'])
        return {
            'status': 'success',
            'retval': retval,
        }
    except ApiError as error:
        return {
            'status': 'error',
            'type': 'ApiError',
            'message': str(error),
        }
