"""Serveradmin - Remote HTTP API

Copyright (c) 2018 InnoGames GmbH
"""

from time import time
from functools import update_wrapper
from logging import getLogger
from base64 import b64decode
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

from paramiko import RSAKey, ECDSAKey, Ed25519Key
from paramiko.message import Message
from paramiko.ssh_exception import SSHException

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

        now = time()
        body = request.body.decode('utf8') if request.body else None
        public_keys = request.META.get('HTTP_X_PUBLICKEYS')
        signatures = request.META.get('HTTP_X_SIGNATURES')
        app_id = request.META.get('HTTP_X_APPLICATION')
        token = request.META.get('HTTP_X_SECURITYTOKEN')
        timestamp = int(request.META['HTTP_X_TIMESTAMP'])

        app = authenticate_app(
            public_keys, signatures, app_id, token, timestamp, now, body
        )

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


def authenticate_app(
    public_keys, signatures, app_id, token, timestamp, now, body
):
    if timestamp + 300 < now:
        raise PermissionDenied('Expired security token')

    if public_keys and signatures:
        app = authenticate_app_ssh(
            public_keys, signatures, timestamp, now, body
        )
    elif app_id and token:
        app = authenticate_app_psk(app_id, token, timestamp, now, body)
    else:
        raise SuspiciousOperation('Missing authentication')

    if app.owner is not None and not app.owner.is_active:
        raise PermissionDenied('Inactive user')

    if app.disabled:
        raise PermissionDenied('Disabled application')

    return app


def authenticate_app_psk(app_id, security_token, timestamp, now, body):
    try:
        app = Application.objects.get(app_id=app_id)
    except Application.DoesNotExist as error:
        raise PermissionDenied(error)

    expected_proof = calc_security_token(app.auth_token, timestamp, body)
    if not constant_time_compare(expected_proof, security_token):
        raise PermissionDenied('Invalid security token')

    return app


def authenticate_app_ssh(public_keys, signatures, timestamp, now, body):
    key_signatures = dict(zip(public_keys.split(','), signatures.split(',')))

    if len(key_signatures) > 20:
        raise SuspiciousOperation('Too many signatures in one request')

    try:
        app = Application.objects.filter(
            auth_token__in=key_signatures.keys()
        ).get()
    except (
        Application.DoesNotExist,
        Application.MultipleObjectsReturned,
    ) as error:
        raise PermissionDenied(error)

    expected_message = str(timestamp) + (':' + body) if body else ''
    public_key = load_public_key(app.auth_token)
    msg = Message(b64decode(key_signatures[app.auth_token]))
    if not public_key.verify_ssh_sig(expected_message.encode(), msg):
        raise PermissionDenied('Invalid signature')

    return app


def load_public_key(base64_public_key):
    # I don't think there is a key type independent way of doing this
    for key_class in (RSAKey, ECDSAKey, Ed25519Key):
        try:
            return key_class(data=b64decode(base64_public_key))
        except SSHException:
            continue

    raise PermissionDenied('Loading public key failed')


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
