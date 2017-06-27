from datetime import timedelta
import logging
import os.path as op
import sys

from django.core.management import call_command
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import mysite
from actions.models import WaterAdministration
from actions.water import today, water_requirement_total, water_requirement_remaining

logger = logging.getLogger(__file__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


class ModelAdminTests(TestCase):
    def setUp(self):
        self.site = mysite
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.csrf_processing_done = True
        self.request = request

    def test_water(self):
        wa = WaterAdministration.objects.all().order_by('date_time').first()
        subj = wa.subject

        wrt = water_requirement_total(subj)

        wrt2 = water_requirement_total(subj, date=today())

        date = today() - timedelta(days=10)
        self.assertTrue(water_requirement_total(subj, date=date) >= 0)

        self.assertTrue(water_requirement_remaining(subj, date=today()) >= 0)

    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)
