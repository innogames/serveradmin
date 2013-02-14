from adminapi.request import PermissionDenied
from adminapi.cmdline.utils import get_auth_token

BASE_URL = 'http://serveradmin.innogames.de/api'

_api_settings = {
    'auth_token': ''
}

def auth(auth_token=None):
    if auth_token is None:
        auth_token = get_auth_token()
        if not auth_token:
            raise Exception('No auth token found')
    _api_settings['auth_token'] = auth_token
