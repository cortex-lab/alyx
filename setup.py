#!/usr/bin/env python3

from getpass import getpass
import os
from shutil import copyfile
import subprocess
import sys
from django.utils.crypto import get_random_string


def _secret_key():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return get_random_string(50, chars)


def _system(cmd):
    print("cmd:", cmd)
    res = os.popen(cmd).read().strip()
    print("out:", res)
    return res
    #process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    #output, error = process.communicate()
    #return output, error


def _psql(sql, **kwargs):
    sql = sql.format(**kwargs)
    cmd = 'sudo -u postgres psql -tc "%s"' % sql
    return _system(cmd)


# Prompt information.
DBNAME = input("Enter a database name [labdb]:") or 'labdb'
DBUSER = input("Enter a postgres username [labdbuser]:") or 'labdbuser'
DBPASSWORD = getpass("Enter a postgres password:") or '123'  # TODO: remove this! for testing only
if not DBPASSWORD:
    print("A password is mandatory.")
    exit(1)
SECRET_KEY = _secret_key()


# Make sure the database exists.
out = _psql("SELECT 1 FROM pg_database WHERE datname = '{DBNAME}'", DBNAME=DBNAME)
if not out:
    out = _psql("CREATE DATABASE {DBNAME}", DBNAME=DBNAME)

# Make sure the user exists.
out = _psql("SELECT 1 FROM pg_user WHERE usename = '{DBUSER}'", DBUSER=DBUSER)
if not out:
    out = _psql("CREATE USER {DBUSER} WITH PASSWORD '{DBPASSWORD}'",
                DBUSER=DBUSER, DBPASSWORD=DBPASSWORD)


# Set up the roles for the user.
_psql("ALTER ROLE {DBUSER} SET client_encoding TO 'utf8';", DBUSER=DBUSER)
_psql("ALTER ROLE {DBUSER} SET default_transaction_isolation TO 'read committed';", DBUSER=DBUSER)
_psql("ALTER ROLE {DBUSER} SET timezone TO 'UTC';", DBUSER=DBUSER)
_psql("GRANT ALL PRIVILEGES ON DATABASE {DBNAME} TO {DBUSER};", DBNAME=DBNAME, DBUSER=DBUSER)
_psql("ALTER USER {DBUSER} WITH CREATEROLE;", DBUSER=DBUSER)
_psql("ALTER USER {DBUSER} WITH SUPERUSER;", DBUSER=DBUSER)
_psql("ALTER USER {DBUSER} WITH CREATEDB;", DBUSER=DBUSER)


# Remove all migration files, that are specific to the cortexlab production server.
_system('rm alyx/*/migrations/0*.py')


# Make sure the virtual environment exists.
_system('virtualenv alyxvenv')


# Set up the settings file.
SETTINGS_SECRET_PATH = 'alyx/alyx/settings_secret.py'
copyfile('alyx/alyx/settings_secret_template.py',
        SETTINGS_SECRET_PATH)
with open(SETTINGS_SECRET_PATH, 'r') as f:
    contents = f.read()

contents = contents.replace('%SECRET_KEY%', SECRET_KEY)
contents = contents.replace('%DBNAME%', DBNAME)
contents = contents.replace('%DBUSER%', DBUSER)
contents = contents.replace('%DBPASSWORD%', DBPASSWORD)

with open(SETTINGS_SECRET_PATH, 'w') as f:
    f.write(contents)


# Install the Python requirements in the virtual environment.
_system('alyxvenv/bin/pip install -r requirements.txt')


# Set up the database.
_system('alyxvenv/bin/python alyx/manage.py makemigrations')
_system('alyxvenv/bin/python alyx/manage.py migrate')


_system('''echo "from django.contrib.auth.models import User;'''
        '''User.objects.create_superuser('admin', 'admin@example.com', 'admin')"'''
        '''| alyxvenv/bin/python alyx/manage.py shell''')
