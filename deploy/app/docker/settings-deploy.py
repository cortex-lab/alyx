"""
Django settings for alyx project.

For more information on this file, see
https://docs.djangoproject.com/en/stable/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/stable/ref/settings/
"""

import os
import json
import logging
import dotenv
from pathlib import Path

from django.conf.locale.en import formats as en_formats

_logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parents[1]  # '/var/www/alyx/alyx'
dotenv_path = BASE_DIR.joinpath('alyx', '.env')
if dotenv_path.exists():
    _logger.warning(f'environment file found: {dotenv_path}')
    dotenv.load_dotenv(dotenv_path=dotenv_path)

# %% Defaults for optional lab settings
# Declared before the lab settings import below so that settings_lab.py overrides them, while
# deployments whose settings_lab.py predates these options still get a usable value.

# Marks this deployment as a public, read-only instance serving released data. It enables
# self-registration and hides lab member records from public users, who may then only see
# redacted users and themselves. Leave False on an internal database.
PUBLIC_DATABASE = False
# Whether a new account must confirm its email address before it can be used. Needs a working
# EMAIL_BACKEND; `manage.py check` warns if this is on without one. How long the confirmation
# link stays valid is governed by Django's PASSWORD_RESET_TIMEOUT (3 days by default), which
# the confirmation token is built on.
PUBLIC_SIGNUP_REQUIRE_VERIFICATION = True
# Usernames that may not be self-registered, either because Alyx reserves them or because they
# are likely to collide with a real lab member arriving in a future data release.
PUBLIC_SIGNUP_RESERVED_USERNAMES = (
    'root', 'admin', 'administrator', 'alyx', 'test', 'public', 'anonymous')

# Extension points for deployments that add their own Django apps, middleware or
# authentication backends. These are folded into INSTALLED_APPS / MIDDLEWARE /
# AUTHENTICATION_BACKENDS after those are defined, which settings_lab.py cannot do for itself
# because it is imported before them.
EXTRA_INSTALLED_APPS = ()
EXTRA_MIDDLEWARE = ()
EXTRA_AUTHENTICATION_BACKENDS = ()

# %% Single sign-on
# Off unless a deployment turns it on. Enabling it requires the optional dependency:
#     pip install alyx[sso]
# and an OAuth/OpenID client registered with the provider. `manage.py check` reports anything
# missing. See the single sign-on section of docs/03_deployment.md for a worked ORCID example.
#
# Identities are held by django-allauth in its own tables, keyed on (provider, uid) - so a
# provider that supplies no email address, as ORCID does not, still identifies its users
# reliably. Those tables only exist on a deployment that enables this.
SSO_ENABLED = False
# django-allauth provider id, e.g. 'orcid', 'google', 'openid_connect'. The matching
# allauth.socialaccount.providers.<id> app is installed automatically.
SSO_PROVIDER = 'orcid'
# Name shown on the sign-in button.
SSO_PROVIDER_NAME = 'ORCID'
# Whether an identity with no matching account may create one. Off by default: on an internal
# database this would let anyone with an account at the provider into Alyx. Turn it on for a
# public database, where self-service registration is the point.
SSO_CREATE_USER = False
# If set, only email addresses in these domains may sign in, e.g. ('example.ac.uk',). Providers
# that supply no email cannot satisfy this, so leave it empty when using one.
SSO_ALLOWED_DOMAINS = ()
# Groups given to accounts created through SSO. On a public database the public users group is
# added to these automatically.
SSO_NEW_USER_GROUPS = ()
# Whether a superuser account may be signed into through SSO. Off by default: superusers can
# change anything in the database, so they are worth keeping on credentials Alyx controls.
SSO_ALLOW_SUPERUSER = False

# Lab-specific settings
from .settings_lab import *  # noqa

# %% Databases
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": os.getenv('POSTGRES_USER', ''),
        "PASSWORD": os.getenv('POSTGRES_PASSWORD', ''),
        "HOST": os.getenv('POSTGRES_HOST', ''),
        "NAME": os.getenv('POSTGRES_DB', ''),
        "PORT": os.getenv('POSTGRES_PORT', '5432')  # Default PostgreSQL port
    }
}
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
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FOLDER_ROOT.joinpath('django.log'),
            'maxBytes': 4 * 1024 * 1024,
            'backupCount': 5,
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
    # Provides django.contrib.admin, with alyx.base.MyAdminSite as the default admin site
    'alyx.apps.AlyxAdminConfig',
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

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

if SSO_ENABLED:
    # django-allauth owns the provider handshake and stores the resulting identity, keyed on
    # (provider, uid). Its backend goes first so that a social login is handled by it; the model
    # backend stays in place so username/password login keeps working alongside SSO.
    EXTRA_INSTALLED_APPS = tuple(EXTRA_INSTALLED_APPS) + (
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        f'allauth.socialaccount.providers.{SSO_PROVIDER}',
    )
    EXTRA_MIDDLEWARE = tuple(EXTRA_MIDDLEWARE) + (
        'allauth.account.middleware.AccountMiddleware',)
    EXTRA_AUTHENTICATION_BACKENDS = (
        ('allauth.account.auth_backends.AuthenticationBackend',)
        + tuple(EXTRA_AUTHENTICATION_BACKENDS))
    # Alyx applies its own sign-in policy and provisioning; see misc/sso.py.
    SOCIALACCOUNT_ADAPTER = 'misc.sso.AlyxSocialAccountAdapter'
    # Provision from the provider's data rather than showing allauth's own signup form: Alyx
    # decides what a new account looks like, and a provider that returns no email address (such
    # as ORCID) has nothing to prefill that form with anyway.
    SOCIALACCOUNT_AUTO_SIGNUP = True
    # allauth does not require an email address by default, which is what lets a provider that
    # supplies none (ORCID) complete a signup rather than being diverted to allauth's own form.
    ACCOUNT_EMAIL_VERIFICATION = 'none'  # the provider is the identity proof, not the address
    # Never store the provider's access/refresh tokens. They are credentials for calling the
    # provider's API, not for authenticating to Alyx, and this database gets dumped and copied.
    SOCIALACCOUNT_STORE_TOKENS = False

INSTALLED_APPS += tuple(EXTRA_INSTALLED_APPS)
AUTHENTICATION_BACKENDS = tuple(EXTRA_AUTHENTICATION_BACKENDS) + AUTHENTICATION_BACKENDS

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

MIDDLEWARE += tuple(EXTRA_MIDDLEWARE)

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
                'misc.context_processors.public_database',
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

THROTTLE_MODE = os.getenv('THROTTLE_MODE', 'user-based').strip().lower()
if THROTTLE_MODE not in ('user-based', 'anonymous'):
    raise ValueError('THROTTLE_MODE must be one of: user-based, anonymous')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'alyx.throttling.BurstRateThrottle',
        'alyx.throttling.SustainedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': os.getenv('THROTTLE_BURST_RATE', '550/minute'),
        'sustained': os.getenv('THROTTLE_SUSTAINED_RATE', None),
        'docs': os.getenv('THROTTLE_DOCS_RATE', '20/minute'),
    },
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'STRICT_JSON': False,
    'DEFAULT_PAGINATION_CLASS': 'alyx.base.LimitedLimitOffsetPagination',
    'EXCEPTION_HANDLER': 'alyx.base.rest_filters_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 250,
}

# Internationalization
USE_I18N = False
USE_L10N = False
USE_TZ = False

STATIC_ROOT = BASE_DIR.joinpath('static')   # /var/www/alyx/alyx/static
STATIC_URL = '/static/'

MEDIA_ROOT = os.getenv('DJANGO_MEDIA_ROOT') or str(BASE_DIR.joinpath('uploaded'))
MEDIA_URL = '/uploaded/'
UPLOADED_IMAGE_WIDTH = 800

# The location for saving and/or serving the cache tables.
# May be a local path, http address or s3 uri (i.e. s3://)
TABLES_ROOT = os.getenv('DJANGO_TABLES_ROOT') or str(BASE_DIR.joinpath('tables'))

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
