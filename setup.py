#!/usr/bin/env python
"""Serveradmin - adminapi - Setup

Copyright (c) 2018 InnoGames GmbH
"""

from setuptools import setup

setup(
    name='adminapi',
    url='https://github.com/innogames/serveradmin',
    author='InnoGames System Administration',
    author_email='it@innogames.com',
    packages=[
        'adminapi',
        'adminapi.dataset',     # XXX Deprecated
        'adminapi.utils',       # XXX Deprecated
    ],
    version='1.2',
    long_description='Serveradmin client library',
    entry_points={
        'console_scripts': [
            'adminapi=adminapi.cli:main',
        ],
    },
)
