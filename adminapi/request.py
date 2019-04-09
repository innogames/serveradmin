"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

import os
from hashlib import sha1
import hmac
from ssl import SSLError
import time
import json
from base64 import b64encode

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
except ImportError:
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError, URLError

try:
    from datetime import datetime, tzinfo, timezone
    # mypy is unhappy about utc beeing either of type UTC or timezone depending
    # on python version. So we settle for the common parent tzinfo here.
    utc = timezone.utc  # type: tzinfo
except ImportError:
    from datetime import datetime, tzinfo, timedelta

    class FakeTimezone(tzinfo):
        """UTC tzinfo implementation

        datetime.timezone was implemented in python3.2, to stay python2
        compatible we implement our own hacky timezones.
        """

        def __init__(self, name, hours=0, minutes=0):
            self._name = name
            self._utcoffset = timedelta(hours, minutes)

        def tzname(self, dt):
            return self._name

        def utcoffset(self, dt):
            return self._utcoffset

        def dst(self, dt):
            return timedelta(0)

    utc = FakeTimezone(name='UTC')

from paramiko.agent import Agent
from paramiko import RSAKey, ECDSAKey, Ed25519Key
from paramiko.message import Message
from paramiko.ssh_exception import SSHException, PasswordRequiredException

from adminapi.cmduser import get_auth_token
from adminapi.filters import BaseFilter
from adminapi.exceptions import ApiError, AuthenticationError


def load_private_key_file(private_key_path):
    """Try to load a private ssh key from disk

    We support RSA, ECDSA and Ed25519 keys and return instances of:
    * paramiko.rsakey.RSAKey
    * paramiko.ecdsakey.ECDSAKey
    * paramiko.ed25519key.Ed25519Key
    """
    # I don't think there is a key type independent way of doing this
    for key_class in (RSAKey, ECDSAKey, Ed25519Key):
        try:
            return key_class.from_private_key_file(private_key_path)
        except PasswordRequiredException as e:
            raise AuthenticationError(e)
        except SSHException:
            continue

    raise AuthenticationError('Loading private key failed')


class Settings:
    base_url = os.environ.get(
        'SERVERADMIN_BASE_URL',
        'https://serveradmin.innogames.de/api'
    )
    auth_key_path = os.environ.get('SERVERADMIN_KEY_PATH')
    auth_key = load_private_key_file(auth_key_path) if auth_key_path else None
    auth_token = os.environ.get('SERVERADMIN_TOKEN') or get_auth_token()
    timeout = 60
    tries = 3
    sleep_interval = 5


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
    message = str(timestamp) + (':' + data) if data else ''
    sig = private_key.sign_ssh_data(message.encode())
    if isinstance(sig, Message):
        # sign_ssh_data returns bytes for agent keys but a Message instance
        # for keys loaded from a file. Fix the file loaded once:
        sig = sig.asbytes()
    return b64encode(sig).decode()


def calc_security_token(auth_token, timestamp, data=None):
    message = str(timestamp) + (':' + data) if data else ''
    return hmac.new(
        auth_token.encode('utf8'), message.encode('utf8'), sha1
    ).hexdigest()


def calc_app_id(auth_token):
    return sha1(auth_token.encode('utf8')).hexdigest()


def send_request(endpoint, get_params=None, post_params=None):
    request = _build_request(endpoint, get_params, post_params)
    for retry in reversed(range(Settings.tries)):
        response = _try_request(request, retry)
        if response:
            break

        # In case of an error, sleep before trying again
        time.sleep(Settings.sleep_interval)
    else:
        assert False    # Cannot happen

    return json.loads(response.read().decode())


def _build_request(endpoint, get_params, post_params):
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
        'X-Timestamp': str(timestamp),
    }

    if Settings.auth_key:
        headers['X-PublicKeys'] = Settings.auth_key.get_base64()
        headers['X-Signatures'] = calc_signature(
            Settings.auth_key, timestamp, post_data
        )
    elif Settings.auth_token:
        headers['X-Application'] = calc_app_id(Settings.auth_token)
        headers['X-SecurityToken'] = calc_security_token(
            Settings.auth_token, timestamp, post_data
        )
    else:
        try:
            agent = Agent()
            agent_keys = agent.get_keys()
        except SSHException:
            raise AuthenticationError('No token and ssh agent found')

        if not agent_keys:
            raise AuthenticationError('No token and ssh agent keys found')

        key_signatures = {
            key.get_base64(): calc_signature(key, timestamp, post_data)
            for key in agent_keys
        }

        headers['X-PublicKeys'] = ','.join(key_signatures.keys())
        headers['X-Signatures'] = ','.join(key_signatures.values())

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
    except (SSLError, URLError):
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
            obj = obj.replace(tzinfo=utc)
        return obj.astimezone(utc).strftime('%Y-%m-%d %H:%M:%S%z')
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
