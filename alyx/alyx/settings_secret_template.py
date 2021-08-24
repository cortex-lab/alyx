# You should edit this file to match your settings and copy it to
# "settings_secret.py".

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '%SECRET_KEY%'

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django_prometheus.db.backends.postgresql',
        'NAME': '%DBNAME%',
        'USER': '%DBUSER%',
        'PASSWORD': '%DBPASSWORD%',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

EMAIL_HOST = 'mail.superserver.net'
EMAIL_HOST_USER = 'alyx@awesomedomain.org'
EMAIL_HOST_PASSWORD = 'UnbreakablePassword'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
