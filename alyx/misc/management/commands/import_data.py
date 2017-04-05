import logging

import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ..importer import import_data
from django.core.management import call_command
import os
import os.path as op


class Command(BaseCommand):
    help = "Imports Google Sheets data into the database"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('data_dir', nargs=1, type=str)

        parser.add_argument(
        '-R', '--remove-pickle', action='store_true',
        dest='remove_pickle', default=False,
        help='Removes and redownloads dumped_google_sheets.pkl')

    def handle(self, *args, **options):

        data_dir = options.get('data_dir')[0]
        if not os.path.isdir(data_dir):
            self.stdout.write('Error: %s is not a directory' % data_dir)
            return

        if options.get('remove_pickle'):
            try:
                os.remove(op.join(data_dir, 'dumped_google_sheets.pkl'))
                self.stdout.write('Removed dumped_google_sheets.pkl')
            except FileNotFoundError:
                self.stdout.write('Could not remove dumped_google_sheets.pkl: file does not exist')
                return

        import_data()
        call_command('migrate')

        json_dir = op.join(data_dir, 'json')

        if not os.path.isdir(data_dir):
            self.stdout.write('Error: %s does not exist: it should contain .json files' % json_dir)
            return

        for root, dirs, files in os.walk(json_dir):
            for file in files:
                if file.endswith('.json'):
                    fullpath = op.join(json_dir, file)
                    call_command('loaddata', fullpath, verbosity=3, interactive=False)

        self.stdout.write(self.style.SUCCESS('Loaded all JSON files from %s' % json_dir))