import urllib2
import hashlib
import hmac
import time
try:
    import simplejson as json
except ImportError:
    import json

from adminapi.cmdline.utils import get_auth_token
from adminapi.utils.json import json_encode_extra

BASE_URL = 'https://serveradmin.innogames.de/api'


def _calc_security_token(auth_token, timestamp, content):
    message = ':'.join((str(timestamp), content))
    return hmac.new(auth_token, message, hashlib.sha1).hexdigest()


def send_request(endpoint, data, auth_token, timeout=None):
    if not auth_token:
        auth_token = get_auth_token()

    data_json = json.dumps(data, default=json_encode_extra)
    try_backup = False

    try:
        req = _build_request(endpoint, auth_token, data_json, try_backup)
        return json.loads(urllib2.urlopen(req, timeout=timeout).read())
    except urllib2.HTTPError as error:
        if error.code in (500, 502):
            try_backup = True
        else:
            raise
    except urllib2.URLError:
        try_backup = True

    if try_backup:
        req = _build_request(endpoint, auth_token, data_json, try_backup)
        return json.loads(urllib2.urlopen(req, timeout=timeout).read())


def _build_request(endpoint, auth_token, data_json, backup=False):
    timestamp = int(time.time())
    application_id = hashlib.sha1(auth_token).hexdigest()
    security_token = _calc_security_token(auth_token, timestamp, data_json)
    headers = {
            'Content-Encoding': 'application/x-json',
            'X-Timestamp': str(timestamp),
            'X-Application': application_id,
            'X-SecurityToken': security_token,
        }
    url = BASE_URL + endpoint

    return urllib2.Request(url, data_json, headers)
