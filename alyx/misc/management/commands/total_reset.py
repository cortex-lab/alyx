import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import psycopg2 as Database
from django.core.management import call_command
from subprocess import call
import os.path as op

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

    def handle(self, *args, **options):
        if args:
            raise CommandError("total_reset takes no arguments")

        if options.get('production'):
            call_command('reset_db', '-R alyx_ro')
        else:
            call_command('reset_db')
        call_command('migrate')

        if not options.get('remove_pickle'):
            call_command('download_gsheets', options.get('data_dir'))
        else:
            call_command('download_gsheets', options.get('data_dir'), '-R')

        call_command('update_zygosities')

        if options.get('production'):
            call(['service apache2 reload'])
