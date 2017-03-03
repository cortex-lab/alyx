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

    def test_1(self):
        ma = SubjectAdmin(Subject, self.site)

        r = ma.changelist_view(self.request)
        self.ar(r)
