import os

from adminapi.utils.cmduser import get_user

def get_auth_token():
    user = get_user()
    config_file = os.path.join(user.pw_dir, '.adminapirc')
    try:
        with open(config_file) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                try:
                    key, value = line.split('=', 1)
                except ValueError:
                    continue
                key, value = key.strip(), value.strip()
                if key == 'auth_token':
                    return value
    except IOError:
        return None
