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


class APIError(Exception):
    def __init__(self, *args, **kwargs):
        if 'status_code' in kwargs:
            self.status_code = kwargs.pop('status_code')
        else:
            self.status_code = 400
        super(Exception, self).__init__(*args, **kwargs)


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
        request = _build_request(endpoint, Settings.auth_token, data_json)
        response = _try_request(request, retry)
        if response:
            break

        # In case of an error, sleep before trying again
        time.sleep(Settings.sleep_interval)
    else:
        assert False    # Cannot happen

    return json.loads(response.read().decode())


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


def _try_request(request, retry=False):
    try:
        return urlopen(request, timeout=Settings.timeout)
    except HTTPError as error:
        if error.code >= 500:
            if retry:
                return None
        elif error.code >= 400:
            content_type = error.info().getheader('Content-Type')
            if content_type == 'application/x-json':
                payload = json.loads(error.read().decode())
                message = payload['error']['message']
                raise APIError(message, status_code=error.code)
        raise
    except URLError:
        if retry:
            return None
        raise


def json_encode_extra(obj):
    if isinstance(obj, BaseFilter):
        return obj.serialize()
    if isinstance(obj, set):
        return list(obj)
    return str(obj)
