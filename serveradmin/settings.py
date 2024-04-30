"""Serveradmin

Copyright (c) 2019 InnoGames GmbH
"""

import os

import environ

env = environ.Env()

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# Take environment variables from .env file
environ.Env.read_env(os.path.join(ROOT_DIR, '../.env'))

SECRET_KEY = env('SECRET_KEY', default=None)

DEBUG = env('DEBUG', default=False)

ALLOWED_HOSTS = env('ALLOWED_HOSTS', default=[])

# Default model used for the implicit generate primary key when no attribute
# of a model as primary_key = True.
#
# See https://docs.djangoproject.com/en/3.2/releases/3.2/#customizing-type-of-auto-created-primary-keys
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Try to connect to a local postgres DB called serveradmin via user based
# authentication by default.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB', default=None),
        'USER': env('POSTGRES_USER', default=None),
        'PASSWORD': env('POSTGRES_PASSWORD', default=None),
        'HOST': env('POSTGRES_HOST', default=None),
        'PORT': env('POSTGRES_PORT', default=5432),
        'OPTIONS': {
            'connect_timeout': 1,
            'client_encoding': 'UTF8',
        },
    },
}

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'netfields',
    'serveradmin.access_control',
    'serveradmin.api',
    'serveradmin.apps',
    'serveradmin.common',
    'serveradmin.graphite',
    'serveradmin.resources',
    'serveradmin.serverdb',
    'serveradmin.servershell',
    'compressor',
]

MENU_TEMPLATES = [
    'servershell/menu.html',
    'resources/menu.html',
]

ROOT_URLCONF = 'serveradmin.urls'

SITE_ID = 1

# Serveradmin itself doesn't provide a login UI as we use the innogames SSO
# django app internally. Luckily django offers a login UI for admins here:
LOGIN_URL = '/admin/login/'

# The one local to rule them all with english UTF-8 encoding and collation
# paired with 24 hour time and ISO 8601 date formatting.
LANGUAGE_CODE = 'en-dk'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = False

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

DATE_FORMAT = 'Y-m-d'
DATETIME_FORMAT = 'Y-m-d H:i:s.uO'

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(ROOT_DIR, '_media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Add compressor to static file finders to allow compressing CSS/JS on the fly
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(ROOT_DIR, '_static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Filename for the logo image file
# This file should reside in the STATIC_ROOT defined above
LOGO_FILENAME = 'logo_innogames_bigbulb_120.png'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'serveradmin.common.context_processors.base',
            ],
            'debug': DEBUG,
            'loaders': [
                (
                    'django.template.loaders.cached.Loader',
                    [
                        'django.template.loaders.filesystem.Loader',
                        'django.template.loaders.app_directories.Loader',
                    ],
                ),
            ],
        },
    },
]

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'serveradmin.wsgi.application'

# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(levelname)s %(asctime)s [%(process)d]: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'level': 'WARNING',
            'handlers': ['console'],
        },
        'serveradmin': {
            'level': 'INFO',
        },
    },
}

OBJECTS_PER_PAGE = 25

GRAPHITE_SPRITE_WIDTH = 150
GRAPHITE_SPRITE_HEIGHT = 100
GRAPHITE_SPRITE_PARAMS = (
    'width=' + str(GRAPHITE_SPRITE_WIDTH) + '&' + 'height=' + str(GRAPHITE_SPRITE_HEIGHT) + '&' + 'graphOnly=true'
)

# Using exec certainly isn't an awesome solution but it's the best we've got.
# The problem boils down to django configs being python files but python only
# imports code from modules in its path.  One solution would be to generate a
# symlink while installing serveradmin, but I don't think there is a way to
# make this work with setuptools and sdist, bdist_wheel and bdist_deb, let
# alone other package managers. Placing the symlink via config management also
# isn't feasable as the symlink would be removed when upgrading the package
# until config management has been run again.
dir_path = os.path.dirname(os.path.realpath(__file__))
for config_path in [
    os.environ.get('SERVERADMIN_CONFIGURATION'),
    dir_path + '/local_settings.py',
    '/etc/serveradmin/settings.py',
]:
    if not config_path:
        continue

    try:
        with open(config_path) as config:
            code = compile(config.read(), config_path, 'exec')
            exec(code)

        print('Serveradmin config loaded from ' + config_path)
        break
    except OSError:
        print("Couldn't load serveradmin config from " + config_path)
