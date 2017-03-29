"""
adapted from http://www.djangosnippets.org/snippets/828/ by dnordberg
"""
import logging

import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import psycopg2 as Database
from ..importer import import_data
from django.core.management import call_command
import os
import os.path as op


class Command(BaseCommand):
    help = "Imports Google Sheets data into the database"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        import_data()
        call_command('migrate')

        for root, dirs, files in os.walk('../data/json'):
            for file in files:
                if file.endswith('.json'):
                    fullpath = op.join(op.dirname( __file__ ), '../../../../', 'data/json', file)
                    call_command('loaddata', fullpath, verbosity=3, interactive=False)


        from subjects.models import ZygosityFinder, Subject

        zf = ZygosityFinder()

        print("Updating the zygosities...")
        for subject in Subject.objects.all():
            zf.genotype_from_litter(subject)
            zf.update_subject(subject)

        self.stdout.write(self.style.SUCCESS('Import successful!'))