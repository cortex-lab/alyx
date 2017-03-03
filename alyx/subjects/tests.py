from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import MyAdminSite, SubjectAdmin
from .models import Subject


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

    def test_subjects_1(self):
        ma = SubjectAdmin(Subject, self.site)

        # List of subjects.
        r = ma.changelist_view(self.request)
        self.ar(r)

        # Get the first subject.
        qs = ma.get_queryset(self.request)
        subj = qs[0]

        # Change page.
        r = ma.change_view(self.request, subj.id.hex)
        self.ar(r)
