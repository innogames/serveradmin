import os
from hashlib import sha1
import hmac
import time

from adminapi.cmduser import get_auth_token
from adminapi.filters import BaseFilter

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

try:
    import simplejson as json
except ImportError:
    import json


class Settings:
    base_url = os.environ.get(
        'SERVERADMIN_BASE_URL',
        'https://serveradmin.innogames.de/api'
    )
    timeout = 60
    tries = 3
    sleep_interval = 5
    auth_token = None


def calc_security_token(auth_token, timestamp, content):
    message = str(timestamp) + ':' + str(content)
    return hmac.new(
        auth_token.encode('utf8'), message.encode('utf8'), sha1
    ).hexdigest()


def calc_app_id(auth_token):
    return sha1(auth_token.encode('utf8')).hexdigest()


def send_request(endpoint, data):
    if not Settings.auth_token:
        Settings.auth_token = get_auth_token()

    data_json = json.dumps(data, default=json_encode_extra)

    for retry in reversed(range(Settings.tries)):
        try:
            req = _build_request(endpoint, Settings.auth_token, data_json)
            return json.loads(
                urlopen(req, timeout=Settings.timeout).read().decode('utf8')
            )
        except HTTPError as error:
            if error.code < 500:
                raise
            if retry <= 0:
                raise
        except URLError:
            if retry <= 0:
                raise

        # In case of an api error, sleep before trying again
        time.sleep(Settings.sleep_interval)


def _build_request(endpoint, auth_token, data_json):
    timestamp = int(time.time())
    app_id = calc_app_id(auth_token)
    security_token = calc_security_token(auth_token, timestamp, data_json)
    headers = {
        'Content-Encoding': 'application/x-json',
        'X-Timestamp': str(timestamp),
        'X-Application': app_id,
        'X-SecurityToken': security_token,
    }
    url = Settings.base_url + endpoint

    return Request(url, data_json.encode('utf8'), headers)


def json_encode_extra(obj):
    if isinstance(obj, BaseFilter):
        return obj.serialize()
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
