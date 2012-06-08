from distutils.core import setup

setup(
    name='adminapi',
    url='http://serveradmin.innogames.de/',
    author='Henning Pridoehl',
    author_email='henning.pridoehl@innogames.de',
    packages=['adminapi', 'adminapi.dataset'],
    version='0.4',
    long_description=('Admin remote API for querying servers and making'
                      'API requests')
)
