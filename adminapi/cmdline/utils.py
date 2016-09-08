import os
from os.path import isfile

from adminapi.utils.cmduser import get_user


def get_auth_token():
    user = get_user()
    config_file = os.path.join(user.pw_dir, '.adminapirc')
    if isfile(config_file):
        with open(config_file) as fp:
            for line in fp:
                if line.startswith('#'):
                    continue
                try:
                    key, value = line.split('=', 1)
                except ValueError:
                    continue
                key, value = key.strip(), value.strip()
                if key == 'auth_token':
                    return value
    raise Exception('No auth token found')
