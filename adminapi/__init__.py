"""Serveradmin - adminapi

Copyright (c) 2018 InnoGames GmbH
"""

from adminapi.request import Settings


# XXX Deprecated
def auth(auth_token=None):
    if auth_token:
        Settings.auth_token = auth_token


# XXX Deprecated
def set_timeout(timeout, what='api'):
    Settings.timeout = timeout
