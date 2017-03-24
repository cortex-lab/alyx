import logging
from operator import attrgetter
import sys
from uuid import UUID

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
        self.site = mysite
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.user = User.objects.get(pk=5)  # default responsible user
        request.csrf_processing_done = True
        self.request = request

    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)

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
        identifier = subj.id.hex if isinstance(subj.id, UUID) else str(subj.id)
        r = ma.change_view(self.request, identifier)
        self.ar(r)

    def test_model_admins(self):
        names = sorted(self.site._registry, key=attrgetter('__name__'))
        for name in names:
            self._test_list_change(self.site._registry[name])
