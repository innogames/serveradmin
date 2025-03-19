"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

import gzip
import hmac
import json
import logging
import os
import time
from base64 import b64encode
from datetime import datetime, timezone
from hashlib import sha1
from http.client import IncompleteRead
from socket import timeout
from ssl import SSLError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paramiko.agent import Agent
from paramiko.message import Message
from paramiko.ssh_exception import PasswordRequiredException, SSHException

from adminapi import VERSION

try:
    from paramiko import ECDSAKey, Ed25519Key, RSAKey

    key_classes = (RSAKey, ECDSAKey, Ed25519Key)
except ImportError:
    # Ed25519Key requires paramiko >= 2.2
    from paramiko import ECDSAKey, RSAKey

    key_classes = (RSAKey, ECDSAKey)

from adminapi.cmduser import get_auth_token
from adminapi.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
)
from adminapi.filters import BaseFilter

logger = logging.getLogger(__name__)


def load_private_key_file(private_key_path):
    """Try to load a private ssh key from disk

    We support RSA, ECDSA and Ed25519 keys and return instances of:
    * paramiko.rsakey.RSAKey
    * paramiko.ecdsakey.ECDSAKey
    * paramiko.ed25519key.Ed25519Key (requires paramiko >= 2.2)
    """
    # I don't think there is a key type independent way of doing this
    for key_class in key_classes:
        try:
            return key_class.from_private_key_file(private_key_path)
        except PasswordRequiredException as e:
            raise AuthenticationError(e)
        except SSHException:
            continue

    raise AuthenticationError('Loading private key failed')


class Settings:
    base_url = os.environ.get('SERVERADMIN_BASE_URL')
    auth_key_path = os.environ.get('SERVERADMIN_KEY_PATH')
    auth_key = load_private_key_file(auth_key_path) if auth_key_path else None
    auth_token = os.environ.get('SERVERADMIN_TOKEN') or get_auth_token()
    timeout = 60.0
    tries = 3
    sleep_interval = 5
    grace_period = 15  # <= serveradmin.api.decorators.TIMESTAMP_GRACE_PERIOD


def calc_message(timestamp, data=None):
    return str(timestamp) + (':' + data) if data else str(timestamp)


def calc_signature(private_key, timestamp, data=None):
    """Create a proof that we posess the private key

    Use paramikos sign_ssh_data to sign the request body together with a
    timestamp. As we send the signature and the timestamp in each request,
    serveradmin can use the public key to check if we have the private key.

    The timestamp is used to prevent a MITM to replay this request over and
    over again. Unfortunately an attacker will still be able to replay this
    message for the grace period serveradmin requires the timestamp to be in.
    we can't prevent this without asking serveradmin for a nonce before every
    request.

    Returns the signature as base64 encoded unicode, ready for transport.
    """
    message = calc_message(timestamp, data)
    sig = private_key.sign_ssh_data(message.encode())
    if isinstance(sig, Message):
        # sign_ssh_data returns bytes for agent keys but a Message instance
        # for keys loaded from a file. Fix the file loaded once:
        sig = sig.asbytes()
    return b64encode(sig).decode()


def calc_signatures(private_keys, timestamp, data=None):
    """Create multiple signatures for all passed keys"""
    sigs = {}
    for key in private_keys:
        try:
            sigs[key.get_base64()] = calc_signature(key, timestamp, data)
        except SSHException:
            # Ignore unusable keys
            pass
    return sigs


def calc_security_token(auth_token, timestamp, data=None):
    message = calc_message(timestamp, data)
    return hmac.new(auth_token.encode('utf8'), message.encode('utf8'), sha1).hexdigest()


def calc_app_id(auth_token):
    return sha1(auth_token.encode('utf8')).hexdigest()


def send_request(endpoint, get_params=None, post_params=None):
    for retry in reversed(range(Settings.tries)):
        request = _build_request(endpoint, get_params, post_params)
        response = _try_request(request, retry)
        if response:
            break

        # In case of an error, sleep before trying again
        time.sleep(Settings.sleep_interval)
    else:
        assert False  # Cannot happen

    content_encoding = response.info().get('Content-Encoding')
    content = response.read()
    if content_encoding == 'gzip':
        content = gzip.decompress(content)

    return json.loads(content)


def _build_request(endpoint, get_params, post_params, retry=1):
    """Wrap request data in an urllib Request instance

    Aside from preparing the get and post data for transport, this function
    authenticates the request using either an auth token or ssh keys.

    Returns an urllib Request.
    """
    if post_params:
        post_data = json.dumps(post_params, default=json_encode_extra)
    else:
        post_data = None

    timestamp = int(time.time())
    headers = {
        'Content-Encoding': 'application/x-json',
        'Accept-Encoding': 'gzip',
        'X-Timestamp': str(timestamp),
        'X-API-Version': '.'.join(str(v) for v in VERSION),
    }

    if Settings.auth_key:
        headers['X-PublicKeys'] = Settings.auth_key.get_base64()
        headers['X-Signatures'] = calc_signature(Settings.auth_key, timestamp, post_data)
    elif Settings.auth_token:
        headers['X-Application'] = calc_app_id(Settings.auth_token)
        headers['X-SecurityToken'] = calc_security_token(Settings.auth_token, timestamp, post_data)
    else:
        try:
            agent = Agent()
            agent_keys = agent.get_keys()
        except SSHException:
            raise AuthenticationError('No token and ssh agent found')

        if not agent_keys:
            raise AuthenticationError('No token and ssh agent keys found')

        key_signatures = calc_signatures(agent_keys, timestamp, post_data)
        if not key_signatures:
            raise AuthenticationError('No token and ssh agent keys found')

        headers['X-PublicKeys'] = ','.join(key_signatures.keys())
        headers['X-Signatures'] = ','.join(key_signatures.values())

    time_spent_signing = int(time.time()) - timestamp
    if time_spent_signing > Settings.grace_period:
        if retry <= Settings.tries:
            logger.error(
                f'Signing the requests took {time_spent_signing} seconds! '
                'Serveradmin would reject this request. Maybe your signing '
                f'soft-/hardware is congested ? Retry {retry}/{Settings.tries}.'
            )
            return _build_request(endpoint, get_params, post_params, retry + 1)

    if not Settings.base_url:
        raise ConfigurationError('Environment variable SERVERADMIN_BASE_URL not set')

    url = Settings.base_url + endpoint
    if get_params:
        url += '?' + urlencode(get_params)
    if post_data:
        post_data = post_data.encode('utf8')

    return Request(url, post_data, headers)


def _try_request(request, retry=False):
    try:
        return urlopen(request, timeout=Settings.timeout)
    except HTTPError as error:
        if error.code >= 500:
            if retry:
                return None
        elif error.code >= 400:
            content_type = error.info()['Content-Type']
            message = str(error)
            if content_type == 'application/x-json':
                payload = json.loads(error.read().decode())
                message = payload['error']['message']
            raise ApiError(message, status_code=error.code)
        raise
    except (SSLError, URLError, timeout, IncompleteRead):
        if retry:
            return None
        raise


def json_encode_extra(obj):
    if isinstance(obj, BaseFilter):
        return obj.serialize()
    if isinstance(obj, datetime):
        # Assume naive datetime objects passed in are in UTC.  This makes sense
        # for python as even datetime.datetime.utcnow() returns naive datetimes
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
