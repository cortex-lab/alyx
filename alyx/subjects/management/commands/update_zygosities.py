from django.core.management import BaseCommand
from subjects.models import ZygosityFinder, Subject


class Command(BaseCommand):
    help = "Updates all automatically generated zygosities from genotype tests"

    def add_arguments(self, parser):
        parser.add_argument('subjects', nargs='*',
                            help='Subject nicknames')

    def handle(self, *args, **options):
        zf = ZygosityFinder()

        self.stdout.write("Updating zygosities...")
        if options.get('subjects'):
            subjects = Subject.objects.filter(nickname__in=options.get('subjects'))
        else:
            subjects = Subject.objects.all()
        for subject in subjects:
            zf.genotype_from_litter(subject)
            zf.update_subject(subject)

        self.stdout.write(self.style.SUCCESS('Updated zygosities!'))
