from django.core.management import BaseCommand
from subjects.models import ZygosityFinder, Subject


class Command(BaseCommand):
    help = "Updates all automatically generated zygosities from genotype tests"

    def handle(self, *args, **options):
        zf = ZygosityFinder()

        self.stdout.write("Updating zygosities...")
        for subject in Subject.objects.all():
            zf.genotype_from_litter(subject)
            zf.update_subject(subject)

        self.stdout.write(self.style.SUCCESS('Updated zygosities!'))
