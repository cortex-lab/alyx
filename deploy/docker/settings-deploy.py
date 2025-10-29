"""
Django settings for alyx project.

For more information on this file, see
https://docs.djangoproject.com/en/stable/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/stable/ref/settings/
"""

import os
import json
import dj_database_url
import logging
import dotenv
import urllib.parse
from pathlib import Path

from django.conf.locale.en import formats as en_formats

_logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parents[1]  # '/var/www/alyx/alyx'
dotenv_path = BASE_DIR.joinpath('alyx', '.env')
if dotenv_path.exists():
    _logger.warning(f'environment file found: {dotenv_path}')
    dotenv.load_dotenv(dotenv_path=dotenv_path)

# Lab-specific settings
from .settings_lab import *  # noqa

# %% Databases
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
# Build the connection URL
POSTGRES_USER = urllib.parse.quote(os.getenv('POSTGRES_USER', ''))
POSTGRES_PASSWORD = urllib.parse.quote(os.getenv('POSTGRES_PASSWORD', ''))
POSTGRES_HOST = urllib.parse.quote(os.getenv('POSTGRES_HOST', ''))
POSTGRES_PORT = urllib.parse.quote(os.getenv('POSTGRES_PORT', '5432'))  # Default PostgreSQL port
POSTGRES_DB = urllib.parse.quote(os.getenv('POSTGRES_DB', ''))
# the database details are provided in the form of an URL. The URL looks like:
# "postgres://USER:PASSWORD@HOST:PORT/DB_NAME"
database_url = f"postgres://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
DATABASES = {"default": dj_database_url.parse(database_url)}
# %% S3 access to write cache tables
# the s3 access details are provided in the form of a JSON string. The variable looks like:
# S3_ACCESS={"access_key":"xxxxx", "secret_key":"xxxxx", "region":"us-east-1"}
if (s3_credentials := os.getenv("S3_ACCESS", None)) is not None:
    S3_ACCESS = json.loads(s3_credentials)

en_formats.DATETIME_FORMAT = "d/m/Y H:i"
DATE_INPUT_FORMATS = ('%d/%m/%Y',)

# Custom User model with UUID primary key
AUTH_USER_MODEL = 'misc.LabMember'
BASE_DIR = Path(__file__).parents[1]  # '/var/www/alyx/alyx'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO')
LOG_FOLDER_ROOT = Path(os.getenv('APACHE_LOG_DIR', BASE_DIR.joinpath('logs')))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            '()': 'colorlog.ColoredFormatter',
            'format': '%(log_color)s%(asctime)s [%(levelname)s] ' +
                      '{%(filename)s:%(lineno)s} %(message)s',
            'datefmt': '%d/%m %H:%M:%S',
            'log_colors': {
                'DEBUG': 'cyan',
                'INFO': 'white',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            },
        },
    },
    'handlers': {
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.FileHandler',
            'filename': LOG_FOLDER_ROOT.joinpath('django.log'),
            'formatter': 'simple'
        },
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': LOG_LEVEL,
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': LOG_LEVEL,
        'propagate': True,
    }
}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", 'False').lower() in ('true', '1', 't')

# ALYX-SPECIFIC
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.eu-west-2.compute.amazonaws.com']
if (web_host := os.getenv('APACHE_SERVER_NAME', '0.0.0.0')) is not None:
    ALLOWED_HOSTS.append(web_host)
CSRF_TRUSTED_ORIGINS = [
    f"http://{web_host}", f"https://{web_host}"]
CSRF_COOKIE_SECURE = True


# Application definition
INSTALLED_APPS = (
    'django_admin_listfilter_dropdown',
    'django_filters',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'mptt',
    'polymorphic',
    'rangefilter',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_docs',
    'reversion',
    'test_without_migrations',
    'actions',
    'data',
    'misc',
    'experiments',
    'jobs',
    'subjects',
    'drf_spectacular',
    'django_cleanup.apps.CleanupConfig',  # needs to be last in the list
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'alyx.base.QueryPrintingMiddleware',
)

ROOT_URLCONF = 'alyx.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

WSGI_APPLICATION = 'alyx.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'STRICT_JSON': False,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'EXCEPTION_HANDLER': 'alyx.base.rest_filters_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 250,
}

# Internationalization
USE_I18N = False
USE_L10N = False
USE_TZ = False

# %% Email configuration
EMAIL_HOST = 'mail.superserver.net'
EMAIL_HOST_USER = 'alyx@awesomedomain.org'
EMAIL_HOST_PASSWORD = 'UnbreakablePassword'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

STATIC_ROOT = BASE_DIR.joinpath('static')   # /var/www/alyx/alyx/static
STATIC_URL = '/static/'

MEDIA_ROOT = os.getenv('DJANGO_MEDIA_ROOT', str(BASE_DIR.joinpath('uploaded')))
MEDIA_URL = '/uploaded/'
UPLOADED_IMAGE_WIDTH = 800

# The location for saving and/or serving the cache tables.
# May be a local path, http address or s3 uri (i.e. s3://)
TABLES_ROOT = os.getenv('DJANGO_TABLES_ROOT', str(BASE_DIR.joinpath('uploaded')))

# storage configurations
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if MEDIA_ROOT.startswith('https://') and '.s3.' in MEDIA_ROOT:
    _logger.warning('S3 backend enabled for uploads and tables')
    STORAGES['default'] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            'bucket_name': 'alyx-uploaded',
            'location': 'uploaded',
            'region_name': 'eu-west-2',
            'addressing_style': 'virtual',
        },
    }
else:
    STORAGES['default'] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
