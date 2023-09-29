#!/usr/bin/env python3
"""Serveradmin and adminapi setup

Copyright (c) 2021 InnoGames GmbH
"""

from setuptools import setup, find_packages
from adminapi import VERSION as SERVERADMIN_VERSION


if __name__ == '__main__':
    setup(
        version='.'.join(map(str, SERVERADMIN_VERSION)),
        name='adminapi',
        description='Serveradmin module',
        url='https://github.com/innogames/serveradmin',
        packages=find_packages(exclude=["serveradmin_*"]),
        package_data={
            'serveradmin.api': ['templates/api/*'],
            'serveradmin.apps': ['templates/apps/*'],
            'serveradmin.common': [
                'static/*',
                'static/css/*',
                'static/icons/*',
                'static/js/*',
                'static/js/plugins/*',
                'templates/*',
                'templates/igrestlogin/*',
            ],
            'serveradmin.graphite': [
                'static/*',
                'static/css/*',
                'static/js/*',
                'templates/graphite/*',
            ],
            'serveradmin.resources': [
                'static/*',
                'static/css/*',
                'static/js/*',
                'templates/resources/*',
            ],
            'serveradmin.serverdb': [
                'static/*',
                'static/css/*',
                'templates/serverdb/*',
            ],
            'serveradmin.servershell': [
                'static/*',
                'static/css/*',
                'static/js/*',
                'static/js/servershell/*',
                'static/js/servershell/autocomplete/*',
                'templates/servershell/*',
                'templates/servershell/modals/*',
            ],
            'serveradmin.nessus': [
                'templates/nessus/*',
            ]
        },
        entry_points={
            'console_scripts': [
                'serveradmin=serveradmin.__main__:main',
                'adminapi=adminapi.__main__:main',
            ],
        },
        install_require=[
            'paramiko',
            'netaddr',
        ],
        author='InnoGames System Administration',
        author_email='it@innogames.com',
    )
