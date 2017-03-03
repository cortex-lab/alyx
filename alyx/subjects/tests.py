from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import *
from .models import *


class MockSuperUser(User):
    def has_perm(self, perm):
        return True

    class Meta:
        proxy = True


class ModelAdminTests(TestCase):
    def setUp(self):
        self.site = MyAdminSite()
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.user = MockSuperUser()
        request.csrf_processing_done = True
        self.request = request

    def ar(self, r):
        assert r.status_code == 200

    def _test_list_change(self, ma):
        # List of subjects.
        r = ma.changelist_view(self.request)
        self.ar(r)

        # Get the first subject.
        qs = ma.get_queryset(self.request)
        if not len(qs):
            return
        subj = qs[0]

        # Change page.
        r = ma.change_view(self.request, subj.id.hex)
        self.ar(r)

    def test_model_admins(self):
        self._test_list_change(SubjectAdmin(Subject, self.site))
        self._test_list_change(CageAdmin(Cage, self.site))
        self._test_list_change(LitterAdmin(Litter, self.site))
        self._test_list_change(LineAdmin(Line, self.site))
        self._test_list_change(SpeciesAdmin(Species, self.site))
        self._test_list_change(StrainAdmin(Strain, self.site))
        self._test_list_change(AlleleAdmin(Allele, self.site))
        self._test_list_change(SourceAdmin(Source, self.site))
        self._test_list_change(SequenceAdmin(Sequence, self.site))
        self._test_list_change(SubjectAdverseEffectsAdmin(Subject, self.site))
