#!/usr/bin/env python3

from getpass import getpass
import os
import os.path as op
import shutil
from django.utils.crypto import get_random_string


def _secret_key():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return get_random_string(50, chars)


def _system(cmd):
    res = os.popen(cmd).read().strip()
    return res


def _psql(sql, **kwargs):
    sql = sql.format(**kwargs)
    cmd = 'sudo -u postgres psql -tc "%s"' % sql
    return _system(cmd)


def _replace_in_file(source_file, target_file, replacements=None, target_mode='w', chmod=None):
    target_file = op.expanduser(target_file)
    #copy2(source_file, target_file)
    with open(source_file, 'r') as f:
        contents = f.read()
    for key, value in replacements.items():
        contents = contents.replace(key, value)
    with open(target_file, target_mode) as f:
        f.write(contents)
    if chmod:
        os.chmod(target_file, chmod)


# Prompt information.
DBNAME = input("Enter a database name [labdb]:") or 'labdb'
DBUSER = input("Enter a postgres username [labdbuser]:") or 'labdbuser'
DBPASSWORD = getpass("Enter a postgres password:")
if not DBPASSWORD:
    print("A password is mandatory.")
    exit(1)
if getpass("Enter a postgres password (again):") != DBPASSWORD:
    print("The passwords don't match.")
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


repl = {
    '%SECRET_KEY%': SECRET_KEY,
    '%DBNAME%': DBNAME,
    '%DBUSER%': DBUSER,
    '%DBPASSWORD%': DBPASSWORD,
}


# Set up the settings file.
_replace_in_file('alyx/alyx/settings_secret_template.py',
                 'alyx/alyx/settings_secret.py',
                 replacements=repl,
                 )


# Set up the .pgpass file to avoid typing the postgres password.
_replace_in_file('scripts/templates/.pgpass_template', '~/.pgpass',
                 replacements=repl, target_mode='a', chmod=0o600)


# Set up the maintainance scripts.
_replace_in_file('scripts/templates/load_db.sh', 'scripts/load_db.sh',
                 replacements=repl, chmod=0o755)
_replace_in_file('scripts/templates/dump_db.sh', 'scripts/dump_db.sh',
                 replacements=repl, chmod=0o755)


# Set up the database.
_system('alyxvenv/bin/python alyx/manage.py makemigrations')
_system('alyxvenv/bin/python alyx/manage.py migrate')


_system('''echo "from misc.models import LabMember;'''
        '''LabMember.objects.create_superuser('admin', 'admin@example.com', 'admin')"'''
        '''| alyxvenv/bin/python alyx/manage.py shell''')
