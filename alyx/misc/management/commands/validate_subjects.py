import logging

from django.core.management.base import BaseCommand

from subjects.models import Subject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("Check and enforce the consistency of subject check boxes (reduced, etc.)")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        subjects = Subject.objects.filter(
            reduced_date__isnull=False, reduced=False).order_by('nickname')
        n = len(subjects)
        print("Check 'reduced' of %s subjects." % n)
        for s in subjects:
            print(" ", s)
        subjects.update(reduced=True)
        print()

        subjects = Subject.objects.filter(
            cull__isnull=False, to_be_culled=True).order_by('nickname')
        n = len(subjects)
        print("Check 'to_be_culled' of %s subjects." % n)
        for s in subjects:
            print(" ", s)
        subjects.update(to_be_culled=False)
