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

from paramiko.message import Message

from adminapi.request import calc_security_token, json_encode_extra
from adminapi.filters import FilterValueError
from serveradmin.apps.models import Application, PublicKey
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
    """Authenticate requests

    Ensure this request isn't beeing replayed by making sure the timestamp
    contained in the request is no older than 300 seconds or raise
    PermissionDenied.

    Hand over the real verification of auth token HMACs to authenticate_app_psk
    or public key signatures to authenticate_app_ssh.

    Ensure that the application and applications owner aren't deactivated or
    raise PermissionDenied.

    Return the app the user authenticated to
    """
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
    """Authenticate request HMAC

    Recreate the security token using the timestamp and body from the request.
    Check if the client send the same security token.

    If they don't match the client doesn't have the correct auth token and we
    raise PermissionDenied.

    Return the app the user authenticated to
    """
    try:
        app = Application.objects.get(app_id=app_id)
    except Application.DoesNotExist as error:
        raise PermissionDenied(error)

    expected_proof = calc_security_token(app.auth_token, timestamp, body)
    if not constant_time_compare(expected_proof, security_token):
        raise PermissionDenied('Invalid security token')

    return app


def authenticate_app_ssh(public_keys, signatures, timestamp, now, body):
    """Authenticate request signature

    Look up if we have exactly one key of the public keys send with this
    request in our database. Use this key to verify the signature send by the
    client.

    If the client sends more then 20 key signature pairs, we raise a
    SuspiciousOperation to prevent DOS.

    If the we find no or more then one matching public key in our database, we
    raise a PermissionDenied. The different applications likely have different
    permissions and we don't want to guess which to enforce if we get more then
    one.

    If the signature doesn't match, we raise a PermissionDenied.

    Return the app the user authenticated to
    """
    key_signatures = dict(zip(public_keys.split(','), signatures.split(',')))

    if len(key_signatures) > 20:
        raise SuspiciousOperation('Over 20 signatures in one request')

    try:
        public_key = PublicKey.objects.filter(
            key_base64__in=key_signatures.keys()
        ).get()
    except (
        PublicKey.DoesNotExist,
        PublicKey.MultipleObjectsReturned,
    ) as error:
        raise PermissionDenied(error)

    expected_message = str(timestamp) + (':' + body) if body else ''
    if not public_key.load().verify_ssh_sig(
        data=expected_message.encode(),
        msg=Message(b64decode(key_signatures[public_key.key_base64]))
    ):
        raise PermissionDenied('Invalid signature')

    return public_key.application


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
