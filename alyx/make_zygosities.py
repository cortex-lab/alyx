import os
import sys
sys.path.append(os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'alyx.settings'
import django
from django.conf import settings
django.setup()

from subjects.models import ZygosityFinder, Subject

zf = ZygosityFinder()

for subject in Subject.objects.all():
    print(subject)
    zf.genotype_from_litter(subject)
    zf.update_subject(subject)
