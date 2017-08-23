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
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import constant_time_compare

from adminapi.utils.json import json_encode_extra
from adminapi.request import calc_security_token
from serveradmin.apps.models import Application
from serveradmin.api import AVAILABLE_API_FUNCTIONS


def api_view(view):     # NOQA: C901
    @csrf_exempt
    def _wrapper(request):
        try:
            app_id = request.META['HTTP_X_APPLICATION']
            timestamp = int(request.META['HTTP_X_TIMESTAMP'])
            security_token = request.META['HTTP_X_SECURITYTOKEN']
        except (KeyError, ValueError):
            return HttpResponseBadRequest(
                'Invalid API request', content_type='text/plain'
            )

        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            return HttpResponseForbidden(
                'Invalid application', content_type='text/plain'
            )

        body = request.body.decode('utf8')
        app = get_object_or_404(Application, app_id=app_id)
        real_token = calc_security_token(app.auth_token, timestamp, body)
        if not constant_time_compare(real_token, security_token):
            return HttpResponseForbidden(
                'Invalid security token', content_type='text/plain'
            )

        if timestamp + 300 < time.time():
            return HttpResponseForbidden(
                'Expired security token', content_type='text/plain'
            )

        if app.owner is not None and not app.owner.is_active:
            return HttpResponseForbidden('Sorry, your user is inactive.')

        if app.disabled:
            return HttpResponseForbidden('Token disabled')

        if not app.superuser and view.__name__ not in [
            'api_call',
            'dataset_commit',
            'dataset_create',
            'dataset_query',
        ]:
            return HttpResponseForbidden('This token has no rights')
        return_value = view(request, app, json.loads(body))
        if getattr(view, 'encode_json', True):
            return_value = json.dumps(return_value, default=json_encode_extra)

        return HttpResponse(return_value, content_type='application/x-json')

    return update_wrapper(_wrapper, view)


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
