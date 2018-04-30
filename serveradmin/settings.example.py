# Django settings for Serveradmin project

import os

DEBUG = True

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

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

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Berlin'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en_DK'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = False

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

SHORT_DATE_FORMAT = 'Y-m-d'
DATE_FORMAT = 'Y-m-d'
SHORT_DATETIME_FORMAT = 'Y-m-d H:M e'
DATETIME_FORMAT = 'Y-m-d H:M:S.fO'
TIME_FORMAT = 'H:M'

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

# Additional locations of static files
STATICFILES_DIRS = [
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
]

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'SET-RANDOM-SECRET-KEY'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
        'DIRS': [os.path.join(ROOT_DIR, 'common/jinja2')],
        'OPTIONS': {'environment': 'serveradmin.jinja2.Environment'},
    },
]

MENU_TEMPLATES = [
    'resources/menu.html',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'serveradmin.api.middleware.ApiMiddleware',
    'serveradmin.hooks.middleware.HooksMiddleware',
]

ROOT_URLCONF = 'serveradmin.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'serveradmin.wsgi.application'

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

# Graphite URL is required to generate graphic URL's.  Normal graphs are
# requested from Graphite on the browser. Small graphs on the overview page are
# requested and stored by the Serveradmin from the Graphite. Graphs are stored
# by the job called "gensprites" under directory graphite/static/graph_sprite.
# They are also merged into single images for every server to reduce the
# requests to the Serveradmin from the browser.
GRAPHITE_URL = 'https://graphite.innogames.de'
GRAPHITE_USER = 'graphite_user'
GRAPHITE_PASSWORD = 'graphite_password'
GRAPHITE_SPRITE_WIDTH = 150
GRAPHITE_SPRITE_HEIGHT = 100
GRAPHITE_SPRITE_PARAMS = (
    'width=' + str(GRAPHITE_SPRITE_WIDTH) + '&' +
    'height=' + str(GRAPHITE_SPRITE_HEIGHT) + '&' +
    'graphOnly=true'
)
# User will be redirected to detailed system overview dashboard
GRAFANA_DASHBOARD = (
    'https://graphite.innogames.de/grafana'
    '/dashboard/db/system-overview'
)
