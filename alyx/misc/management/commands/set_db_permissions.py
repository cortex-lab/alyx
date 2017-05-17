"""
adapted from http://www.djangosnippets.org/snippets/828/ by dnordberg
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import psycopg2 as Database


class Command(BaseCommand):
    help = "Resets the database."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
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
        owner = options.get('owner') or user
        ro_user = options.get('ro_user') or None

        database_name = options.get('dbname') or dbinfo.get('NAME') or database_name
        if database_name == '':
            raise CommandError("You need to specify DATABASE_NAME in your Django settings file.")

        database_host = dbinfo.get('HOST') or database_host
        database_port = dbinfo.get('PORT') or database_port

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

        # Recreate and grant perms
        query = "GRANT ALL ON SCHEMA public TO public;"
        if owner:
            query += "GRANT ALL ON SCHEMA public TO %s; " % owner

        if ro_user:
            query += "GRANT USAGE ON SCHEMA public TO %s;" % ro_user
            query += "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO %s;" % ro_user
            query += "GRANT SELECT ON ALL TABLES IN SCHEMA public TO %s;" % ro_user

        logging.info('Executing... "' + query + '"')
        cursor.execute(query)
