"""Serveradmin - Remote HTTP API

Copyright (c) 2019 InnoGames GmbH
"""

from datetime import datetime, timedelta
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
from django.utils import timezone, dateformat

from paramiko.message import Message

from adminapi.request import (
    calc_message,
    calc_security_token,
    json_encode_extra,
)
from adminapi.filters import FilterValueError
from serveradmin.apps.models import Application, PublicKey
from serveradmin.api import AVAILABLE_API_FUNCTIONS

logger = getLogger('serveradmin')

# Acceptable offset between what the clients believes the time was when it made
# the request and the time on the serveradmin server when the request is beeing
# handled.  Chosen by a fair dice role.
TIMESTAMP_GRACE_PERIOD = timedelta(seconds=16)


def api_view(view):
    @csrf_exempt
    def _wrapper(request):
        logger.debug('api: Start processing request: {} {}'.format(
            request.scheme, request.path
        ))

        now = timezone.now()
        body = request.body.decode('utf8') if request.body else None
        public_keys = request.META.get('HTTP_X_PUBLICKEYS')
        signatures = request.META.get('HTTP_X_SIGNATURES')
        app_id = request.META.get('HTTP_X_APPLICATION')
        token = request.META.get('HTTP_X_SECURITYTOKEN')
        then = datetime.utcfromtimestamp(
            int(request.META['HTTP_X_TIMESTAMP'])
        ).replace(tzinfo=timezone.utc)
        body_json = json.loads(body) if body else None
        status_code = 200

        try:
            app = authenticate_app(
                public_keys, signatures, app_id, token, then, now, body
            )
            return_value = view(request, app, body_json)

            logger.info('api: Call: ' + (', '.join([
                'Method: {}'.format(view.__name__),
                'Application: {}'.format(app),
                'Time elapsed: {:.3f}s'.format(
                    (timezone.now() - now).total_seconds()
                ),
            ])))
        except (
            FilterValueError,
            ValidationError,
            PermissionDenied,
            ObjectDoesNotExist,
            SuspiciousOperation,
        ) as error:
            reason = ''

            if isinstance(
                error,
                (FilterValueError, ValidationError, SuspiciousOperation)
            ):
                status_code = 400
                reason = 'Bad Request'
            if isinstance(error, PermissionDenied):
                status_code = 403
                reason = 'Forbidden'
            if isinstance(error, ObjectDoesNotExist):
                status_code = 404
                reason = 'Not Found'

            message = '{}: {}'.format(reason, str(error))
            logger.error('api: {}'.format(message))
            return_value = {
                'error': {
                    'message': message,
                }
            }

        return HttpResponse(
            json.dumps(return_value, default=json_encode_extra),
            content_type='application/x-json',
            status=status_code,
        )

    return update_wrapper(_wrapper, view)


def authenticate_app(
    public_keys, signatures, app_id, token, then, now, body
):
    """Authenticate requests

    Ensure this request isn't beeing replayed by making sure the timestamp
    contained in the request is no more than TIMESTAMP_GRACE_PERIOD seconds
    removed from the current server time or raise PermissionDenied.

    Hand over the real verification of auth token HMACs to authenticate_app_psk
    or public key signatures to authenticate_app_ssh.

    Ensure that the application and applications owner aren't deactivated or
    raise PermissionDenied.

    Return the app the user authenticated to
    """
    if (
        then + TIMESTAMP_GRACE_PERIOD < now or
        then - TIMESTAMP_GRACE_PERIOD > now
    ):
        raise PermissionDenied(
            'Request expired, header timestamp off by {:0.0f} seconds'
            .format((now - then).total_seconds())
        )

    timestamp = dateformat.format(then, u'U')
    if public_keys and signatures:
        app = authenticate_app_ssh(public_keys, signatures, timestamp, body)
    elif app_id and token:
        app = authenticate_app_psk(app_id, token, timestamp, body)
    else:
        raise SuspiciousOperation('Missing authentication')

    if app.owner is not None and not app.owner.is_active:
        raise PermissionDenied('Inactive user {}'.format(app.owner.id))

    if app.disabled:
        raise PermissionDenied('Disabled application {}'.format(app.id))

    # Note when this app was last used. We don't update this information more
    # than once every minute. Some apps authenticate thousand of times per
    # minute, that would be a lot of useless commits.
    if not app.last_login or (now - app.last_login) > timedelta(minutes=1):
        app.last_login = now
        app.save()

    return app


def authenticate_app_psk(app_id, security_token, timestamp, body):
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


def authenticate_app_ssh(public_keys, signatures, timestamp, body):
    """Authenticate request signature

    If the client sends more then 20 key signature pairs, we raise a
    SuspiciousOperation to prevent DOS.

    Look up all of the public keys send with this request in our database.
    Verify the signature send by the client for those public keys we know
    about. Raise PermissionDenied for invalid signatures.

    If we find no public key in our database, we raise a PermissionDenied.

    If we find multiple valid signatures using public keys belonging to
    different applications, we raise PermissionDenied. The different
    applications likely have different permissions and we don't want to guess
    which to enforce.

    Return the app the user authenticated to
    """

    def verify_signature(public_key, signature):
        """Verify a single signature

        Raise PermissionDenied if the signature is invalid

        Return the public key on success
        """
        expected_message = calc_message(timestamp, body)
        if not public_key.load().verify_ssh_sig(
            data=expected_message.encode(),
            msg=Message(b64decode(signature))
        ):
            raise PermissionDenied('Invalid signature')

        return public_key

    key_signatures = dict(zip(public_keys.split(','), signatures.split(',')))
    if len(key_signatures) > 20:
        raise SuspiciousOperation('Over 20 signatures in one request')

    verified_keys = {
        verify_signature(public_key, key_signatures[public_key.key_base64])
        for public_key in PublicKey.objects.filter(
            key_base64__in=key_signatures.keys()
        )
    }

    if not verified_keys:
        raise PermissionDenied('No known public key found')

    applications = {key.application for key in verified_keys}
    if len(applications) > 1:
        raise PermissionDenied(
            'Valid signatures for more than one application received: ' +
            ', '.join([str(key) for key in verified_keys]) +
            '. It is unclear which ACLs to enforce, giving up.'
        )

    application = applications.pop()
    if not application:
        # This can never happen as the PublicKey.application is not nullable,
        # this is only a safety net in case this field gets changed.
        raise SuspiciousOperation('We did not end up with an application')

    return application


def api_function(group, name=None):
    def inner_decorator(fn):
        group_dict = AVAILABLE_API_FUNCTIONS.setdefault(group, {})
        fn_name = fn.__name__ if name is None else name
        group_dict[fn_name] = fn
        return fn

    return inner_decorator
