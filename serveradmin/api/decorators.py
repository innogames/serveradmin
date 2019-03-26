"""Serveradmin - Remote HTTP API

Copyright (c) 2018 InnoGames GmbH
"""

from time import time
from functools import update_wrapper
from logging import getLogger
import json

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    SuspiciousOperation,
    ValidationError,
)
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import constant_time_compare

from adminapi.request import calc_security_token, json_encode_extra
from adminapi.filters import FilterValueError
from serveradmin.apps.models import Application
from serveradmin.api import AVAILABLE_API_FUNCTIONS

logger = getLogger('serveradmin')


def api_view(view):
    @csrf_exempt
    def _wrapper(request):
        logger.debug('api: Start processing request: {} {}'.format(
            request.scheme, request.path
        ))

        try:
            app_id = request.META['HTTP_X_APPLICATION']
            token = request.META['HTTP_X_SECURITYTOKEN']
            timestamp = int(request.META['HTTP_X_TIMESTAMP'])
        except (KeyError, ValueError) as error:
            raise SuspiciousOperation(error)

        now = time()
        body = request.body.decode('utf8') if request.body else None

        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist as error:
            raise PermissionDenied(error)
        authenticate_app(app, token, timestamp, now, body)

        body_json = json.loads(body) if body else None
        try:
            status_code = 200
            return_value = view(request, app, body_json)
        except (
            FilterValueError, ObjectDoesNotExist, ValidationError
        ) as error:
            status_code = 404 if isinstance(error, ObjectDoesNotExist) else 400
            return_value = {
                'error': {
                    'message': str(error),
                }
            }

        logger.info('api: Call: ' + (', '.join([
            'Method: {}'.format(view.__name__),
            'Application: {}'.format(app),
            'Time elapsed: {:.3f}s'.format(time() - now),
        ])))
        return HttpResponse(
            json.dumps(return_value, default=json_encode_extra),
            content_type='application/x-json',
            status=status_code,
        )

    return update_wrapper(_wrapper, view)


def authenticate_app(app, token, timestamp, now, body):
    if timestamp + 300 < now:
        raise PermissionDenied('Expired security token')

    real_token = calc_security_token(app.auth_token, timestamp, body)
    if not constant_time_compare(real_token, token):
        raise PermissionDenied('Invalid security token')

    if app.owner is not None and not app.owner.is_active:
        raise PermissionDenied('Inactive user')

    if app.disabled:
        raise PermissionDenied('Disabled application')


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
