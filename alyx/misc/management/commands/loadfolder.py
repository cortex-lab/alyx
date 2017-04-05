import logging

import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
import os
import os.path as op


class Command(BaseCommand):
    help = "Imports a whole folder of .json files into the database"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('json_dir', nargs=1, type=str)

    def handle(self, *args, **options):

        json_dir = options.get('json_dir')[0]

        if not os.path.isdir(json_dir):
            self.stdout.write('Error: %s does not exist: it should contain .json files' % json_dir)
            return

        for root, dirs, files in os.walk(json_dir):
            for file in files:
                if file.endswith('.json'):
                    fullpath = op.join(json_dir, file)
                    call_command('loaddata', fullpath, verbosity=3, interactive=False)

        self.stdout.write(self.style.SUCCESS('Loaded all JSON files from %s' % json_dir))
