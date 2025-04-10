"""Serveradmin

Copyright (c) 2020 InnoGames GmbH
"""

import functools
import logging
import os
import re
import time
from base64 import b64encode

_hostname_re = re.compile(
    r'^(?=.{1,255}$)[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}'
    r'[0-9A-Za-z])?(?:\.[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}'
    r'[0-9A-Za-z])?)*\.?$'
)


def validate_hostname(hostname):
    return _hostname_re.match(hostname) is not None


def random_alnum_string(length):
    # This length might look weird, but it is basically just the number
    # of bytes required to get the wanted length plus the number of bytes
    # to read to remove special chars without failing below the length.
    read_length = ((length // 4) + 1) * 3 + (int(length * 0.03) // 3) * 3
    while True:
        random_bytes = os.urandom(read_length)
        random_str = b64encode(random_bytes, b'??').decode().replace('?', '')
        if len(random_str) >= length:
            return random_str[:length]


def profile(func):
    @functools.wraps(func)
    def wrapper_profile(*args, **kwargs):
        start = time.perf_counter()
        value = func(*args, **kwargs)
        end = time.perf_counter()

        duration = end - start
        msg = '%s processed in %s ms' % (func.__name__, int(duration * 1000))
        logging.getLogger('profile').info(msg)

        return value

    return wrapper_profile
