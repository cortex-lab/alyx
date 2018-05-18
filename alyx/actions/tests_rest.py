from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.timezone import now

from alyx.base import BaseTests
from subjects.models import Subject


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.subject = Subject.objects.all().first()
        # Set an implant weight.
        self.subject.implant_weight = 4.56
        self.subject.save()

    def test_create_weighing(self):
        url = reverse('weighing-create')
        data = {'subject': self.subject, 'weight': 12.3}
        response = self.client.post(url, data)
        self.ar(response, 201)
        d = response.data
        self.assertTrue(d['date_time'])
        self.assertEqual(d['subject'], self.subject.nickname)
        self.assertEqual(d['weight'], 12.3)

    def test_create_water_administration(self):
        url = reverse('water-administration-create')
        data = {'subject': self.subject, 'water_administered': 1.23}
        response = self.client.post(url, data)
        self.ar(response, 201)
        d = response.data
        self.assertTrue(d['date_time'])
        self.assertEqual(d['subject'], self.subject.nickname)
        self.assertEqual(d['water_administered'], 1.23)

    def test_list_water_administration(self):
        url = reverse('water-administration-create')
        response = self.client.get(url)
        self.ar(response)
        d = response.data[0]
        self.assertTrue(set(('date_time', 'url', 'subject', 'user',
                             'water_administered', 'hydrogel')) <= set(d))

    def test_list_weighing(self):
        url = reverse('weighing-create')
        response = self.client.get(url)
        self.ar(response)
        d = response.data[0]
        self.assertTrue(set(('date_time', 'url', 'subject', 'user', 'weight')) <= set(d))

    def test_water_requirement(self):
        # Create water administered and weighing.
        self.client.post(reverse('water-administration-create'),
                         {'subject': self.subject, 'water_administered': 1.23})
        self.client.post(reverse('weighing-create'),
                         {'subject': self.subject, 'weight': 12.3})

        url = reverse('water-requirement-detail', kwargs={'nickname': self.subject.nickname})

        date = now().date()
        response = self.client.get(url + '?start_date=%s&end_date=%s' % (date, date))
        self.ar(response)
        d = response.data
        self.assertEqual(d['subject'], self.subject.nickname)
        self.assertEqual(d['implant_weight'], 4.56)
        self.assertTrue(set(('date', 'weight_measured', 'weight_expected', 'water_expected',
                             'water_given', 'hydrogel_given',)) <= set(d['records'][0]))
