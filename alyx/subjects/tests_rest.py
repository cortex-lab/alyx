from django.contrib.auth.models import User
from django.urls import reverse
from alyx.base import BaseTests

from rest_framework import status


class APISubjectsTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

    def test_list_subjects(self):
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        assert len(d) > 200
        assert set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0])
