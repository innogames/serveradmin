"""Serveradmin

Copyright (c) 2018 InnoGames GmbH
"""

import os

DEBUG = False

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# Try to connect to a local postgres DB called serveradmin via user based
# authentication by default.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'serveradmin',
        'OPTIONS': {
            'connect_timeout': 1,
            'client_encoding': 'UTF8',
        },
    },
}

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'serveradmin.api.middleware.ApiMiddleware',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'markup_deprecated',
    'netfields',
    'serveradmin.access_control',
    'serveradmin.api',
    'serveradmin.apps',
    'serveradmin.common',
    'serveradmin.graphite',
    'serveradmin.resources',
    'serveradmin.serverdb',
    'serveradmin.servershell',
]

MENU_TEMPLATES = [
    'resources/menu.html',
]

ROOT_URLCONF = 'serveradmin.urls'

SITE_ID = 1

# Serveradmin itself doesn't provide a login UI as we use the innogames SSO
# django app internally. Luckily django offers a login UI for admins here:
LOGIN_URL = '/admin/login/'

# The one local to rule them all with english UTF-8 encoding and collation
# paired with 24 hour time and ISO 8601 date formatting.
LANGUAGE_CODE = 'en_DK'

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

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(ROOT_DIR, '_static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

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
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'APP_DIRS': True,
    },
]

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'serveradmin.wsgi.application'

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s [%(process)d]: %(message)s',
        }
    },
    'handlers': {
        'logfile': {
            'class': 'logging.FileHandler',
            'filters': ['require_debug_false'],
            'level': 'INFO',
            'formatter': 'verbose',
            'filename': '/var/log/serveradmin.log',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['require_debug_true'],
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'serveradmin': {
            'handlers': ['logfile', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

OBJECTS_PER_PAGE = 25

GRAPHITE_SPRITE_WIDTH = 150
GRAPHITE_SPRITE_HEIGHT = 100
GRAPHITE_SPRITE_PARAMS = (
    'width=' + str(GRAPHITE_SPRITE_WIDTH) + '&' +
    'height=' + str(GRAPHITE_SPRITE_HEIGHT) + '&' +
    'graphOnly=true'
)

from serveradmin.local_settings import *  # NOQA: F401, F403

if 'EXTRA_MIDDLEWARE_CLASSES' in locals():
    MIDDLEWARE_CLASSES += EXTRA_MIDDLEWARE_CLASSES
if 'EXTRA_INSTALLED_APPS' in locals():
    INSTALLED_APPS += EXTRA_INSTALLED_APPS
if 'EXTRA_MENU_TEMPLATES' in locals():
    MENU_TEMPLATES += EXTRA_MENU_TEMPLATES
