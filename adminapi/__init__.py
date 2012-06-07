#BASE_URL = 'https://serveradmin.innogames.de/api'
BASE_URL = 'http://localhost:8000/api'

_api_settings = {
    'auth_token': ''
}

def auth(auth_token):
    _api_settings['auth_token'] = auth_token
