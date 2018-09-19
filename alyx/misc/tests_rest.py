from django.urls import reverse
from django.contrib.auth import get_user_model
from alyx.base import BaseTests


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

    def test_create_lab(self):
        response = self.client.post(reverse('lab-list'), {'name': 'superlab'})
        self.ar(response, 201)
        d = response.data
        self.assertTrue(d['name'])
