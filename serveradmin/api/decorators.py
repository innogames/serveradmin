import time
from functools import update_wrapper
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


def api_view(view):
    @csrf_exempt
    def _wrapper(request):
        problem = check_authentication_headers(request)
        if problem:
            return HttpResponseBadRequest(problem, content_type='text/plain')

        app_id = request.META['HTTP_X_APPLICATION']
        security_token = request.META['HTTP_X_SECURITYTOKEN']
        timestamp = int(request.META['HTTP_X_TIMESTAMP'])
        body = request.body.decode('utf8')

        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            problem = 'No such application'
        else:
            problem = authenticate_app(app, security_token, timestamp, body)
        if problem:
            return HttpResponseForbidden(problem, content_type='text/plain')

        return_value = view(request, app, json.loads(body))
        if getattr(view, 'encode_json', True):
            return_value = json.dumps(return_value, default=json_encode_extra)

        return HttpResponse(return_value, content_type='application/x-json')

    return update_wrapper(_wrapper, view)


def check_authentication_headers(request):
    for header_name in ['APPLICATION', 'SECURITYTOKEN', 'TIMESTAMP']:
        header = 'HTTP_X_' + header_name
        if header not in request.META:
            return 'Missing header "{}"'.format(header)

    if not request.META['HTTP_X_TIMESTAMP'].isdecimal():
        return 'Malformatted header "HTTP_X_TIMESTAMP"'


def authenticate_app(app, security_token, timestamp, body):
    real_token = calc_security_token(app.auth_token, timestamp, body)
    if not constant_time_compare(real_token, security_token):
        return 'Invalid security token'

    if timestamp + 300 < time.time():
        return 'Expired security token'

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
