"""Serveradmin - adminapi

Copyright (c) 2018 InnoGames GmbH
"""

import os
from os.path import isfile
from os.path import expanduser


def get_auth_token():
    user_home = expanduser('~')
    config_file = os.path.join(user_home, '.adminapirc')
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
