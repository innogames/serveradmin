#!/usr/bin/env python3
"""Serveradmin and adminapi setup

Copyright (c) 2019 InnoGames GmbH
"""

from setuptools import setup, find_packages
from serveradmin import VERSION as SERVERADMIN_VERSION


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
                'templates/*',
                'templates/igrestlogin/*',
            ],
            'serveradmin.graphite': [
                'static/graphite/*',
                'templates/graphite/*',
            ],
            'serveradmin.resources': ['templates/resources/*'],
            'serveradmin.serverdb': [
                'static/*',
                'templates/serverdb/*',
            ],
            'serveradmin.servershell': [
                'static/*',
                'static/css/*',
                'static/js/*',
                'static/js/servershell/*',
                'static/js/servershell/autocomplete/*',
                'templates/servershell/*',
                'templates/servershell/index/*',
                'templates/servershell/index/modals/*',
            ],
        },
        entry_points={
            'console_scripts': [
                'serveradmin=serveradmin.__main__:main',
                'adminapi=adminapi.__main__:main',
            ],
        },
        author='InnoGames System Administration',
        author_email='it@innogames.com',
    )
