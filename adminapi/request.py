import hashlib
import hmac
import time

from adminapi.cmdline.utils import get_auth_token
from adminapi.utils.json import json_encode_extra

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError, URLError

try:
    import simplejson as json
except ImportError:
    import json

# BASE_URL = 'https://serveradmin.innogames.de/api'
BASE_URL = 'http://127.0.0.1:8000/api'


def calc_security_token(auth_token, timestamp, content):
    message = str(timestamp) + ':' + str(content)
    return hmac.new(
        auth_token.encode('utf8'), message.encode('utf8'), hashlib.sha1
    ).hexdigest()


def send_request(endpoint, data, auth_token, timeout=None):
    if not auth_token:
        auth_token = get_auth_token()

    data_json = json.dumps(data, default=json_encode_extra)
    try_backup = False

    try:
        req = _build_request(endpoint, auth_token, data_json, try_backup)
        return json.loads(urlopen(req, timeout=timeout).read().decode('utf8'))
    except HTTPError as error:
        if error.code in (500, 502):
            try_backup = True
        else:
            raise
    except URLError:
        try_backup = True

    if try_backup:
        req = _build_request(endpoint, auth_token, data_json, try_backup)
        return json.loads(urlopen(req, timeout=timeout).read().decode('utf8'))


def _build_request(endpoint, auth_token, data_json, backup=False):
    timestamp = int(time.time())
    application_id = hashlib.sha1(auth_token.encode('utf8')).hexdigest()
    security_token = calc_security_token(auth_token, timestamp, data_json)
    headers = {
        'Content-Encoding': 'application/x-json',
        'X-Timestamp': str(timestamp),
        'X-Application': application_id,
        'X-SecurityToken': security_token,
    }
    url = BASE_URL + endpoint

    return Request(url, data_json.encode('utf8'), headers)
