"""
adapted from http://www.djangosnippets.org/snippets/828/ by dnordberg
"""
import logging

import psycopg2 as Database

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Resets the database."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--noinput', action='store_false',
            dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.')
        parser.add_argument(
            '-D', '--dbname', action='store', dest='dbname', default=None,
            help='Use another database name than defined in settings.py')
        parser.add_argument(
            '-R', '--read-only-user', action='store', dest='ro_user', default=None,
            help='Grant SELECT permissions to this read-only user')

    def handle(self, *args, **options):
        if args:
            raise CommandError("reset_db takes no arguments")

        router = 'default'
        dbinfo = settings.DATABASES.get(router)
        if dbinfo is None:
            raise CommandError("Unknown database router %s" % router)

        user = password = database_name = database_host = database_port = ''

        user = options.get('user') or dbinfo.get('USER') or user
        password = options.get('password') or dbinfo.get('PASSWORD') or password

        database_name = options.get('dbname') or dbinfo.get('NAME') or database_name
        if database_name == '':
            raise CommandError("You need to specify DATABASE_NAME in your Django settings file.")

        database_host = dbinfo.get('HOST') or database_host
        database_port = dbinfo.get('PORT') or database_port

        verbosity = int(options.get('verbosity', 1))
        if options.get('interactive'):
            confirm = input("""
You have requested a database reset.
This will IRREVERSIBLY DESTROY
ALL data in the database "%s".
Are you sure you want to do this?
Type 'yes' to continue, or 'no' to cancel: """ % (database_name,))
        else:
            confirm = 'yes'

        if confirm != 'yes':
            print("Reset cancelled.")
            return

        conn_params = {'database': database_name}
        if user:
            conn_params['user'] = user
        if password:
            conn_params['password'] = password
        if database_host:
            conn_params['host'] = database_host
        if database_port:
            conn_params['port'] = database_port

        connection = Database.connect(**conn_params)
        connection.set_isolation_level(0)  # autocommit false
        cursor = connection.cursor()

        # Now let's do the dirty work
        drop_query = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        logging.info('Executing... "' + drop_query + '"')
        try:
            cursor.execute(drop_query)
        except Database.ProgrammingError as e:
            logging.exception("Error: %s" % str(e))

        args = ('set_db_permissions',)
        if options.get('ro_user'):
            args += ('-R', options.get('ro_user'))
        if options.get('dbname'):
            args += ('-D', options.get('dbname'))
        call_command(*args)

        if verbosity >= 2 or options.get('interactive'):
            self.stdout.write(self.style.SUCCESS('Reset successful!'))
