from django.contrib.auth.models import User
from django.urls import reverse
from alyx.base import BaseTests
from actions.models import WaterAdministration, Weighing


class APISubjectsTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

    def test_list_subjects(self):
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 200)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date',
                             'line', 'litter', 'sex', 'genotype', 'url')) <= set(d[0]))

    def test_list_alive_subjects(self):
        url = reverse('subject-list') + '?alive=True&stock=True'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 200)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0]))

        # also test that you can get some back when asking for non-stock
        url = reverse('subject-list') + '?alive=True&stock=False'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        self.assertTrue(len(d) > 0)
        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0]))

    def test_subject_1(self):
        # test the individual subject endpoint, i.e. when you ask for a subject by name
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        # Ask for the first subject
        response = self.client.get(d[0]['url'])
        self.ar(response)
        d = response.data

        self.assertTrue(set(('nickname', 'id', 'responsible_user', 'death_date', 'line', 'litter',
                             'sex', 'genotype', 'url', 'water_requirement_total',
                             'water_requirement_remaining', 'weighings',
                             'water_administrations')) <= set(d))

    def test_subject_water_administration(self):
        subject = WaterAdministration.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue('water_administrations' in d)
        self.assertTrue(d['water_administrations'])
        wa = set(d['water_administrations'][0])
        self.assertTrue(set(('date_time', 'water_administered', 'hydrogel', 'url')) <= wa)

    def test_subject_weighing(self):
        subject = Weighing.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue('weighings' in d)
        self.assertTrue(d['weighings'])
        w = set(d['weighings'][0])
        self.assertTrue(set(('date_time', 'weight', 'url')) <= w)

    def test_subject_restricted(self):
        url = reverse('water-restricted-subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        self.assertTrue(set(('nickname', 'water_requirement_total',
                             'water_requirement_remaining')) <= set(d[0]))
