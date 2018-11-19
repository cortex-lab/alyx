import logging
import sys

from django.core.management.base import BaseCommand
from misc.models import Lab
from subjects.models import Subject

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


class Command(BaseCommand):
    help = "One-off migration script for UCL"

    def handle(self, *args, **options):
        if Lab.objects.filter(name='cortexlab'):
            print("Cortexlab lab already exists. Aborting.")
            return
        lab = Lab.objects.create(
            pk='4027da48-7be3-43ec-a222-f75dffe36872',
            name='cortexlab',
            institution='University College London',
            address='Cruciform Building, Gower Street, London, WC1E 6BT, United Kingdom',
            timezone='Europe/London',
            reference_weight_pct=0.,
            zscore_weight_pct=.8,
        )
        Subject.objects.all().update(lab=lab)
        print("All subjects updated with lab %s" % lab)
