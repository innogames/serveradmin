#!/usr/bin/env python3

"""Serveradmin and adminapi setup

Copyright (c) 2026 InnoGames GmbH
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
                'static/webfonts/*',
                'static/js/servershell/*',
                'static/js/servershell/autocomplete/*',
                'templates/servershell/*',
                'templates/servershell/modals/*',
            ],
        },
        entry_points={
            'console_scripts': [
                'serveradmin=serveradmin.__main__:main',
                'adminapi=adminapi.__main__:main',
            ],
        },
        install_requires=[
            'paramiko>=2.7,<4',
            'netaddr>=0.8.0,<1.4.0',
        ],
        python_requires=">=3.9,<3.14",
        author='InnoGames System Administration',
        author_email='it@innogames.com',
    )
