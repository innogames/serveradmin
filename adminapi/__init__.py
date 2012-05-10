BASE_URL = 'https://serveradmin.innogames.de/api'

_api_settings = {
    'auth_token': None
}

def auth(auth_token):
    _api_settings['auth_token'] = auth_token
