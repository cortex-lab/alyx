import os.path as op
import subprocess
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command


class Command(BaseCommand):
    help = "Total reset - delete data, reimport from Google Sheets"

    def add_arguments(self, parser):

        default_data_dir = op.join(op.dirname(__file__), '../../../../data/')

        parser.add_argument(
            '-P', '--production', action='store_true', dest='production', default=False,
            help='Sets alyx_ro permissions and restarts apache2')
        parser.add_argument(
            '-d', '--data-dir', action='store', dest='data_dir', default=default_data_dir,
            help='Specify alternate data directory')
        parser.add_argument(
            '-R', '--remove-pickle', action='store_true',
            dest='remove_pickle', default=False,
            help='Removes and redownloads dumped_google_sheets.pkl')
        parser.add_argument(
            '-M', '--make-migrations', action='store_true',
            dest='make_migrations', default=False,
            help='Makes all app migrations before migrating')

    def handle(self, *args, **options):
        if settings.DEBUG is False:
            sys.stdout.write("This command is disabled in production.\n")
            return
        if args:
            raise CommandError("total_reset takes no arguments")

        if options.get('production'):
            call_command('reset_db', '-R alyx_ro')
        else:
            call_command('reset_db')

        if options.get('make_migrations'):
            call_command('makemigrations', 'actions', 'behavior', 'data', 'electrophysiology',
                         'equipment', 'imaging', 'misc', 'subjects')

        call_command('migrate')

        if options.get('production'):
            call_command('set_db_permissions', '-R alyx_ro')
        else:
            call_command('set_db_permissions')

        if not options.get('remove_pickle'):
            call_command('download_gsheets', options.get('data_dir'))
        else:
            call_command('download_gsheets', options.get('data_dir'), '-R')

        call_command('update_zygosities')
        call_command('set_user_permissions')

        if options.get('production'):
            subprocess.check_call("sudo service apache2 restart".split())
