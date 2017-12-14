from time import time
from functools import update_wrapper
from logging import getLogger
try:
    import simplejson as json
except ImportError:
    import json

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import constant_time_compare

from adminapi.request import calc_security_token, json_encode_extra
from serveradmin.apps.models import Application
from serveradmin.api import AVAILABLE_API_FUNCTIONS

logger = getLogger('serveradmin')


def api_view(view):
    @csrf_exempt
    def _wrapper(request):
        logger.debug('api: Start processing request: {} {}'.format(
            request.scheme, request.path
        ))

        problem = check_authentication_headers(request)
        if problem:
            logger.error('api: Bad request: ' + problem)
            return HttpResponseBadRequest(problem, content_type='text/plain')

        app_id = request.META['HTTP_X_APPLICATION']
        token = request.META['HTTP_X_SECURITYTOKEN']
        timestamp = int(request.META['HTTP_X_TIMESTAMP'])
        now = time()
        body = request.body.decode('utf8')

        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            problem = 'No such application'
        else:
            if timestamp + 300 < now:
                problem = 'Expired security token'
            else:
                problem = authenticate_app(app, token, timestamp, body)
        if problem:
            logger.error('api: Forbidden: ' + problem)
            return HttpResponseForbidden(problem, content_type='text/plain')

        return_value = view(request, app, json.loads(body))
        if getattr(view, 'encode_json', True):
            return_value = json.dumps(return_value, default=json_encode_extra)

        logger.info('api: Call: ' + (', '.join([
            'Method: {}'.format(view.__name__),
            'Application: {}'.format(app),
            'Time elapsed: {:.3f}s'.format(time() - now),
        ])))
        return HttpResponse(return_value, content_type='application/x-json')

    return update_wrapper(_wrapper, view)


def check_authentication_headers(request):
    for header_name in ['APPLICATION', 'SECURITYTOKEN', 'TIMESTAMP']:
        header = 'HTTP_X_' + header_name
        if header not in request.META:
            return 'Missing header "{}"'.format(header)

    if not request.META['HTTP_X_TIMESTAMP'].isdecimal():
        return 'Malformatted header "HTTP_X_TIMESTAMP"'


def authenticate_app(app, token, timestamp, body):
    real_token = calc_security_token(app.auth_token, timestamp, body)
    if not constant_time_compare(real_token, token):
        return 'Invalid security token'

    if app.owner is not None and not app.owner.is_active:
        return 'Inactive user'

    if app.disabled:
        return 'Disabled application'


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
