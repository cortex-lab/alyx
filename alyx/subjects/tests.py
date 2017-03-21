import logging
import sys

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import *
from .models import *

logger = logging.getLogger(__file__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


class ModelAdminTests(TestCase):
    def setUp(self):
        self.site = MyAdminSite()
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.user = User.objects.get(username='charu')
        request.csrf_processing_done = True
        self.request = request

    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped'), verbosity=1)

    def ar(self, r):
        r.render()
        self.assertTrue(r.status_code == 200)

    def _test_list_change(self, ma):
        # List of subjects.
        r = ma.changelist_view(self.request)
        self.ar(r)

        # Get the first subject.
        qs = ma.get_queryset(self.request)
        logger.debug("Found %d items for %s.", len(qs), qs.model)
        if not len(qs):
            return
        subj = qs[0]

        # Change page.
        r = ma.change_view(self.request, subj.id.hex)
        self.ar(r)

    def test_model_admins(self):
        self._test_list_change(SubjectAdmin(Subject, self.site))
        self._test_list_change(BreedingPairAdmin(BreedingPair, self.site))
        self._test_list_change(LitterAdmin(Litter, self.site))
        self._test_list_change(LineAdmin(Line, self.site))
        self._test_list_change(SpeciesAdmin(Species, self.site))
        self._test_list_change(StrainAdmin(Strain, self.site))
        self._test_list_change(AlleleAdmin(Allele, self.site))
        self._test_list_change(SourceAdmin(Source, self.site))
        self._test_list_change(SequenceAdmin(Sequence, self.site))
        self._test_list_change(SubjectAdverseEffectsAdmin(Subject, self.site))
