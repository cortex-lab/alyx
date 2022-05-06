#!/usr/bin/env python3

from pathlib import Path
from getpass import getpass
import os
import os.path as op
import platform
from django.utils.crypto import get_random_string
import sys
from warnings import warn

MACOS = platform.system() == 'Darwin'


def _secret_key():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return get_random_string(50, chars)


def _system(cmd):
    res = os.popen(cmd).read().strip()
    return res


def _psql(sql, **kwargs):
    sql = sql.format(**kwargs)
    if MACOS:
        cmd = 'psql -tc "{}"'.format(sql)
    else:
        cmd = 'sudo su - postgres -c "psql -tc \\"{}\\""'.format(sql)
    return _system(cmd)


def _replace_in_file(source_file, target_file, replacements=None, target_mode='w', chmod=None):
    target_file = op.expanduser(target_file)
    replacements = {} if replacements is None else replacements
    #copy2(source_file, target_file)
    with open(source_file, 'r') as f:
        contents = f.read()
    for key, value in replacements.items():
        contents = contents.replace(key, value)
    with open(target_file, target_mode) as f:
        f.write(contents)
    if chmod:
        os.chmod(target_file, chmod)


# Check if we are inside a virtual environment
if not MACOS and not hasattr(sys, 'real_prefix') and sys.base_prefix == sys.prefix:
    warn('You are not currently in a virtual environment, '
         'would you like to proceed anyway? (y/n): ', RuntimeWarning)
    continue_anyway = input()
    if continue_anyway not in ("y", 'yes'):
        print('Create a virtual environment from the repository root with: '
              '"virtualenv alyxvenv --python=python3"')
        print('Enter a virtual environment from the repository root with: '
              '"source alyxvenv/bin/activate"')
        sys.exit()


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
try:
    _psql("ALTER ROLE {DBUSER} SET client_encoding TO 'utf8';", DBUSER=DBUSER)
    _psql("ALTER ROLE {DBUSER} SET default_transaction_isolation TO 'read committed';",
          DBUSER=DBUSER)
    _psql("ALTER ROLE {DBUSER} SET timezone TO 'UTC';", DBUSER=DBUSER)
    _psql("GRANT ALL PRIVILEGES ON DATABASE {DBNAME} TO {DBUSER};", DBNAME=DBNAME, DBUSER=DBUSER)
    _psql("ALTER USER {DBUSER} WITH CREATEROLE;", DBUSER=DBUSER)
    _psql("ALTER USER {DBUSER} WITH SUPERUSER;", DBUSER=DBUSER)
    _psql("ALTER USER {DBUSER} WITH CREATEDB;", DBUSER=DBUSER)
    print('-----------------------------')
    print('Database successfully created')
except Exception as e:
    print('Could not create database, error message:\n')
    raise e


file_log = Path('/var/log/alyx').joinpath(f"{DBNAME}.log")
file_log_json = Path('/var/log/alyx').joinpath(f"{DBNAME}_json.log")
repl = {
    '%SECRET_KEY%': SECRET_KEY,
    '%DBNAME%': DBNAME,
    '%DBUSER%': DBUSER,
    '%DBPASSWORD%': DBPASSWORD,
    '%ALYX_JSON_LOG_FILE%': str(file_log_json),
    '%ALYX_LOG_FILE%': str(file_log)
}

try:
    _replace_in_file('alyx/alyx/settings_template.py',
                     'alyx/alyx/settings.py', replacements=repl)
    _replace_in_file('alyx/alyx/settings_lab_template.py',
                     'alyx/alyx/settings_lab.py')
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
    print('Configuration files successfully created from templates')
except Exception as e:
    print('Could not create configuration from templates, error message:\n')
    raise e


# Set up the database.
try:
    _system(f'sudo mkdir -p {file_log_json.parent}')
    _system(f'sudo mkdir -p {file_log.parent}')
    _system(f'sudo chown {os.getlogin()}:www-data -fR {file_log.parent}')
    _system(f'sudo chown {os.getlogin()}:www-data -fR {file_log_json.parent}')
    _system(f'touch {file_log_json}')
    _system(f'touch {file_log}')
    _system('python3 alyx/manage.py makemigrations')
    _system('python3 alyx/manage.py migrate')

    _system('''echo "from misc.models import LabMember;'''
            '''LabMember.objects.create_superuser('admin', 'admin@example.com', 'admin')"'''
            '''| python3 alyx/manage.py shell''')
    print('Database successfully configured for Alyx')
except Exception as e:
    print('Could not configure database for Alyx, error message:\n')
    raise e

print('------------------------')
print('Alyx setup successful <3')
