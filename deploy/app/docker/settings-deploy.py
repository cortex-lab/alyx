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
from textwrap import dedent

from alyx import __version__

from django.conf.locale.en import formats as en_formats

_logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parents[1]  # '/var/www/alyx/alyx'
dotenv_path = BASE_DIR.joinpath('alyx', '.env')
if dotenv_path.exists():
    _logger.warning(f'environment file found: {dotenv_path}')
    dotenv.load_dotenv(dotenv_path=dotenv_path)

# %% Defaults for optional lab settings
# Declared before the settings_lab import so that lab settings override them.

# Public read-only instance: enables self-registration and hides lab members from public users.
PUBLIC_DATABASE = False
# Require email confirmation before an account works. Needs a working EMAIL_BACKEND; the link
# expires after PASSWORD_RESET_TIMEOUT.
PUBLIC_SIGNUP_REQUIRE_VERIFICATION = True
# Mailing preferences offered at sign-up, as {field name: checkbox label}. Empty disables the
# feature and its page entirely; consent to be emailed is specific to a public database.
EMAIL_PREFERENCES = {}
# Usernames that may not be self-registered.
PUBLIC_SIGNUP_RESERVED_USERNAMES = (
    'root', 'admin', 'administrator', 'alyx', 'test', 'public', 'anonymous')

# %% Sign-up bot protection
# Protects outbound mail rather than accounts: bounces over ~5% suspend SES sending. The hidden
# honeypot field is always on. See misc/antibot.py.

# Per-address cap as (count, seconds). Leave off where courses run - a lecture theatre shares one
# address - since the honeypot and Turnstile still apply there.
PUBLIC_SIGNUP_THROTTLE = None
# Addresses exempt from the cap above.
PUBLIC_SIGNUP_THROTTLE_EXEMPT = ()
# Only trust X-Forwarded-For behind a proxy known to set it; clients can otherwise spoof it.
PUBLIC_SIGNUP_TRUST_FORWARDED_FOR = False
# Cloudflare Turnstile. Both keys must be set to enable it.
TURNSTILE_SITE_KEY = os.getenv('TURNSTILE_SITE_KEY', '')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')

# Folded into INSTALLED_APPS / MIDDLEWARE / AUTHENTICATION_BACKENDS below, which settings_lab.py
# cannot do itself as it is imported before them.
EXTRA_INSTALLED_APPS = ()
EXTRA_MIDDLEWARE = ()
EXTRA_AUTHENTICATION_BACKENDS = ()

# %% Single sign-on
# Needs the optional dependency: pip install alyx[sso]. `manage.py check` reports what is
# missing; see the single sign-on section of docs/03_deployment.md.
SSO_ENABLED = False
# django-allauth provider id; the matching provider app is installed automatically.
SSO_PROVIDER = 'orcid'
# Name shown on the sign-in button.
SSO_PROVIDER_NAME = 'ORCiD'
# Whether an identity with no account may create one. On an internal database this would admit
# anyone holding a provider account.
SSO_CREATE_USER = False
# Restrict sign-in to these email domains. Unusable with a provider that supplies no email.
SSO_ALLOWED_DOMAINS = ()
# Groups given to accounts SSO creates; a public database adds the public users group too.
SSO_NEW_USER_GROUPS = ()
# Whether a superuser may sign in through SSO. Off: superusers can change anything.
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
    # Alyx applies its own sign-in policy and provisioning; see misc/signup/sso.py.
    SOCIALACCOUNT_ADAPTER = 'misc.signup.sso.AlyxSocialAccountAdapter'
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
    # allauth allocates usernames for SSO accounts and checks each candidate against this
    # list, so the names Alyx reserves are honoured on that path too - without it, a provider
    # supplying a preferred_username of "root" would be taken at face value.
    ACCOUNT_USERNAME_BLACKLIST = PUBLIC_SIGNUP_RESERVED_USERNAMES
    # New SSO accounts land on the preferences page: a provider such as ORCiD supplies no email
    # address, so this is the first chance to offer one. Signup only, not every sign-in.
    ACCOUNT_SIGNUP_REDIRECT_URL = '/me/preferences'

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

# %% OpenAPI schema (/api/schema, rendered at /docs)
# Without these drf-spectacular reports an empty title and version 0.0.0, which is its own
# placeholder rather than anything meaningful. Alyx has no API version independent of the
# application - the endpoints are the application - so the schema reports the Alyx version,
# which also tells a client which release it is talking to.
SPECTACULAR_SETTINGS = {
    'TITLE': 'Alyx REST API',
    'VERSION': __version__,
    'SERVE_INCLUDE_SCHEMA': False,  # the schema endpoint itself is not interesting to document
    'DESCRIPTION': dedent(f"""
        The REST interface to this Alyx database. Most clients reach it through
        [ONE](https://int-brain-lab.github.io/ONE/) rather than directly.

        ## Authentication

        Every endpoint requires authentication. Requests carry a token in the `Authorization`
        header:

            Authorization: Token 1a2b3c4d...

        There are two ways to get one.

        **From your account page.** Sign in and open [/me](/me), which shows your token and can
        regenerate it if it leaks. This is the only route for accounts that sign in through an
        identity provider, since those have no password.

        **From the `/auth-token` endpoint**, if your account has a password:

            curl -X POST -d "username=<username>&password=<password>" \\
                 https://{os.getenv('APACHE_SERVER_NAME', 'your-alyx-host')}/auth-token

        ## Using ONE

        Sign in once, with whichever credential your account has. If it has a password, give
        your username and ONE will ask for the password:

            from one.api import ONE
            one = ONE(base_url='https://{os.getenv('APACHE_SERVER_NAME', 'your-alyx-host')}',
                      username='<username>')

        If it has no password - an account that signs in through an identity provider - give
        the token instead. ONE asks the database who it belongs to, so no username is needed:

            from one.api import ONE
            one = ONE(base_url='https://{os.getenv('APACHE_SERVER_NAME', 'your-alyx-host')}',
                      token='<token>')

        Either way, ONE remembers, so from then on it is just:

            from one.api import ONE
            one = ONE()

        There is no need to call `ONE.setup()`, and no need to pass the username or token
        again. Pass one again only to switch accounts, or after regenerating a token.
        """),
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
