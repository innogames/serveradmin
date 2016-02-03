from distutils.core import setup

setup(
    name='adminapi',
    url='https://serveradmin.innogames.de/',
    author='Henning Pridoehl',
    author_email='henning.pridoehl@innogames.de',
    packages=(
        'adminapi',
        'adminapi.dataset',
        'adminapi.utils',
        'adminapi.api',
        'adminapi.cmdline',
    ),
    version='0.58',
    long_description=(
        'Admin remote API for querying servers and making API requests'
    ),
)
