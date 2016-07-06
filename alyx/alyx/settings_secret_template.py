# You should edit this file to match your settings and copy it to "settings_secret.py".

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ab5d+*w*er&*ym32k33x6p6v$v+3_pmrf%e3eg-_9+0%2lu-1)'

# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'labdb',
        'USER': 'labdb',
        'PASSWORD': 'abcdefg',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}