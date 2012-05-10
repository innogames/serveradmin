import json
import urllib2
import hashlib
import hmac
import time

from adminapi.utils import json_encode_extra

def _calc_security_token(auth_token, timestamp, content):
    message = ':'.join((str(timestamp), content))
    return hmac.new(auth_token, message, hashlib.sha1).hexdigest()

def send_request(url, data, auth_token):
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
    return json.loads(urllib2.urlopen(req).read())
