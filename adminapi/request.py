import urllib2
import hashlib
import hmac
import time
try:
    import simplejson as json
except ImportError:
    import json

from adminapi.utils.json import json_encode_extra

class PermissionDenied(Exception):
    pass

def _calc_security_token(auth_token, timestamp, content):
    message = ':'.join((str(timestamp), content))
    return hmac.new(auth_token, message, hashlib.sha1).hexdigest()

def send_request(url, data, auth_token, timeout=None):
    if not auth_token:
        raise ValueError("No auth token supplied. Try adminapi.auth('Token').")

    data_json = json.dumps(data, default=json_encode_extra)
    timestamp = int(time.time())
    application_id = hashlib.sha1(auth_token).hexdigest()
    security_token = _calc_security_token(auth_token, timestamp, data_json)
    headers = {
        'Content-Encoding': 'application/x-json',
        'X-Timestamp': str(timestamp),
        'X-Application': application_id,
        'X-SecurityToken': security_token
    }

    req = urllib2.Request(url, data_json, headers)
    retries = 3
    while True:
        retries -= 1
        try:
            return json.loads(urllib2.urlopen(req, timeout=timeout).read())
        except urllib2.HTTPError, e:
            if e.code == 403:
                raise PermissionDenied(e.read())
            elif e.code == 502:
                if retries <= 0:
                    raise
                time.sleep(5)
            else:
                raise
        except urllib2.URLError:
            if retries <= 0:
                raise
            time.sleep(5)
