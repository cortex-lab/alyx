# You should edit this file to match your settings and copy it to
# "settings_secret.py".

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '%SECRET_KEY%'

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': '%DBNAME%',
        'USER': '%DBUSER%',
        'PASSWORD': '%DBPASSWORD%',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}
