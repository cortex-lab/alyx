from django.contrib.auth.models import User
from django.urls import reverse

from alyx.base import BaseTests
from subjects.models import Subject


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.subject = Subject.objects.all().first()

    def test_create_weighing(self):
        url = reverse('weighing-create')
        data = {'subject': self.subject, 'weight': 12.3}
        response = self.client.post(url, data)
        self.ar(response, 201)
        d = response.data
        assert d['date_time']
        assert d['subject'] == self.subject.nickname
        assert d['weight'] == 12.3

    def test_create_water_administration(self):
        url = reverse('water-administration-create')
        data = {'subject': self.subject, 'water_administered': 1.23}
        response = self.client.post(url, data)
        self.ar(response, 201)
        d = response.data
        assert d['date_time']
        assert d['subject'] == self.subject.nickname
        assert d['water_administered'] == 1.23
