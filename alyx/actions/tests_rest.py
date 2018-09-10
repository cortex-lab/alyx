from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.timezone import now

from alyx.base import BaseTests
from subjects.models import Subject


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.superuser2 = get_user_model().objects.create_superuser('test2', 'test2', 'test2')
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

    def test_list_water_administration_1(self):
        url = reverse('water-administration-create')
        response = self.client.get(url)
        self.ar(response)
        d = response.data[0]
        self.assertTrue(set(('date_time', 'url', 'subject', 'user',
                             'water_administered', 'hydrogel')) <= set(d))

    def test_list_water_administration_filter(self):
        url = reverse('water-administration-create')
        data = {'subject': self.subject, 'water_administered': 1.23}
        response = self.client.post(url, data)

        url = reverse('water-administration-create') + '?nickname=' + self.subject.nickname
        response = self.client.get(url)
        self.ar(response)
        d = response.data[0]
        self.assertTrue(set(('date_time', 'url', 'subject', 'user',
                             'water_administered', 'hydrogel')) <= set(d))

    def test_list_weighing_1(self):
        url = reverse('weighing-create')
        response = self.client.get(url)
        self.ar(response)
        d = response.data[0]
        self.assertTrue(set(('date_time', 'url', 'subject', 'user', 'weight')) <= set(d))

    def test_list_weighing_filter(self):
        url = reverse('weighing-create')
        data = {'subject': self.subject, 'weight': 12.3}
        response = self.client.post(url, data)

        url = reverse('weighing-create') + '?nickname=' + self.subject.nickname
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

        url = reverse('water-requirement', kwargs={'nickname': self.subject.nickname})

        date = now().date()
        response = self.client.get(url + '?start_date=%s&end_date=%s' % (date, date))
        self.ar(response)
        d = response.data
        self.assertEqual(d['subject'], self.subject.nickname)
        self.assertEqual(d['implant_weight'], 4.56)
        self.assertTrue(set(('date', 'weight_measured', 'weight_expected', 'water_expected',
                             'water_given', 'hydrogel_given',)) <= set(d['records'][0]))

    def test_sessions(self):
        ses_dict = {'subject': self.subject,
                    'users': self.superuser,
                    'narrative': 'auto-generated-session, test',
                    'start_time': '2018-07-09T12:34:56',
                    'end_time': '2018-07-09T12:34:57',
                    'type': 'Base',
                    'number': '1',
                    'parent_session': ''}
        # Test the session creation
        r = self.client.post(reverse('session-list'), ses_dict)
        self.ar(r, 201)
        s1 = r.data
        ses_dict['start_time'] = '2018-07-11T12:34:56'
        ses_dict['end_time'] = '2018-07-11T12:34:57'
        ses_dict['users'] = [self.superuser, self.superuser2]
        r = self.client.post(reverse('session-list'), ses_dict)
        s2 = r.data
        # Test the date range filter
        r = self.client.get(reverse('session-list') + '?date_range=2018-07-09,2018-07-09')
        self.assertEqual(r.data[0], s1)
        # Test the user filter, this should return 2 sessions
        r = self.client.get(reverse('session-list') + '?users=test')
        self.assertTrue(len(r.data) == 2)
        # This should return only one session
        r = self.client.get(reverse('session-list') + '?users=test2')
        self.assertEqual(r.data[0], s2)
