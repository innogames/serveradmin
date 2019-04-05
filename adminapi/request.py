"""Serveradmin - adminapi

Copyright (c) 2019 InnoGames GmbH
"""

import os
from hashlib import sha1
import hmac
from ssl import SSLError
import time
import json
import base64

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

from adminapi.cmduser import get_auth_token
from adminapi.filters import BaseFilter
from adminapi.exceptions import ApiError


class Settings:
    base_url = os.environ.get(
        'SERVERADMIN_BASE_URL',
        'https://serveradmin.innogames.de/api'
    )
    auth_token = os.environ.get('SERVERADMIN_TOKEN') or get_auth_token()
    timeout = 60
    tries = 3
    sleep_interval = 5


def calc_signed_security_token(agent_key, timestamp, data=None):
    """Used for ssh key auth"""
    security_token = calc_security_token(
        agent_key.get_base64(), timestamp, data
    )
    sig = agent_key.sign_ssh_data(security_token.encode())
    return base64.encodestring(sig).decode()


def calc_security_token(auth_token, timestamp, data=None):
    message = str(timestamp)
    if data:
        message += ':' + data
    return hmac.new(
        auth_token.encode('utf8'), message.encode('utf8'), sha1
    ).hexdigest()


def calc_app_id(auth_token):
    return sha1(auth_token.encode('utf8')).hexdigest()


def send_request(endpoint, get_params=None, post_params=None):
    request = _build_request(
        endpoint, Settings.auth_token, get_params, post_params
    )
    for retry in reversed(range(Settings.tries)):
        response = _try_request(request, retry)
        if response:
            break

        # In case of an error, sleep before trying again
        time.sleep(Settings.sleep_interval)
    else:
        assert False    # Cannot happen

    return json.loads(response.read().decode())


def _build_request(endpoint, auth_token, get_params, post_params):
    if post_params:
        post_data = json.dumps(post_params, default=json_encode_extra)
    else:
        post_data = None

    timestamp = int(time.time())
    headers = {
        'Content-Encoding': 'application/x-json',
        'X-Timestamp': str(timestamp),
    }

    if auth_token:
        headers['X-Application'] = calc_app_id(auth_token)
        headers['X-SecurityToken'] = calc_security_token(
            auth_token, timestamp, post_data
        )
    else:
        try:
            agent = Agent()
        except Exception:
            raise Exception('No auth token and ssh agent found')
        headers['X-Signatures'] = json.dumps([
            {
                'public_key': auth_key.get_base64(),
                'signature': calc_signed_security_token(
                    auth_key, timestamp, post_data
                ),
            } for auth_key in agent.get_keys()
        ])

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
