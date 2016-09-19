from adminapi.cmdline.utils import get_auth_token

_api_settings = {
    'auth_token': '',
    'timeout_api': None,
    'timeout_dataset': 60,
}


def auth(auth_token=None):
    if auth_token is None:
        auth_token = get_auth_token()
    _api_settings['auth_token'] = auth_token


def set_timeout(timeout, what='api'):
    if what == 'api':
        _api_settings['timeout_api'] = timeout
    elif what == 'dataset':
        _api_settings['timeout_dataset'] = timeout
    else:
        raise ValueError('Unknown timeout: {0}'.format(what))
