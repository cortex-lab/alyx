import logging

from django.core.management.base import BaseCommand

from subjects.models import Subject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("Check and enforce the consistency of subject check boxes (reduced, etc.)")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        subjects = Subject.objects.filter(reduced_date__isnull=False, reduced=False)
        n = len(subjects)
        subjects.update(reduced=True)
        self.stdout.write("Check 'reduced' of %s subjects." % n)

        subjects = Subject.objects.filter(death_date__isnull=False, to_be_culled=True)
        n = len(subjects)
        subjects.update(to_be_culled=False)
        self.stdout.write("Check 'to_be_culled' of %s subjects." % n)
