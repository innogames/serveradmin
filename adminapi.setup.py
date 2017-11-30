#!/usr/bin/env python

from distutils.core import setup

setup(
    name='adminapi',
    url='https://serveradmin.innogames.de/',
    author='InnoGames System Administration',
    author_email='it@innogames.com',
    packages=[
        'adminapi',
        'adminapi.dataset',
        'adminapi.utils',
        'adminapi.cmdline',
    ],
    version='1.0',
    long_description=(
        'Admin remote API for querying servers and making API requests'
    ),
    entry_points={
        'console_scripts': [
            'adminapi=adminapi.cli:main',
        ],
    },
)
