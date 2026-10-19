from datetime import datetime
from unittest import mock
from pathlib import Path
import json
import tempfile

from django.urls import reverse
from django.contrib.auth import get_user_model

from alyx.base import BaseTests
from misc.models import Enrichment, Housing, HousingSubject, LabMembership, Lab
from misc.views import _get_cache_info
from data.models import Tag
from subjects.models import Subject


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.lab = Lab.objects.create(name='basement')
        self.public_user = get_user_model().objects.create(
            username='troublemaker', password='azerty', is_public_user=True)
        self.public_user.allowed_users.set([self.superuser])

    def test_create_lab_membership(self):
        # first test creation of lab through rest endpoint
        response = self.post(reverse('lab-list'), {'name': 'superlab'})
        d = self.ar(response, 201)
        self.assertTrue(d['name'])
        # create a membership
        lm = LabMembership.objects.create(user=self.superuser, lab=self.lab)
        # date should be populated as default
        self.assertTrue(lm.start_date.date() == datetime.now().date())
        self.assertTrue(self.superuser.lab == [self.lab.name])
        # create an expired membership, should change output
        lm = LabMembership.objects.create(user=self.superuser,
                                          start_date=datetime(2018, 9, 1),
                                          end_date=datetime(2018, 10, 1),
                                          lab=Lab.objects.get(name='superlab'))
        self.assertTrue(self.superuser.lab == [self.lab.name])
        lm.end_date = None
        lm.save()
        self.assertTrue(set(self.superuser.lab) == set(['superlab', self.lab.name]))
        # now makes sure the REST endpoint returns the same thing
        response = self.client.get(reverse('user-list') + '/test')
        d = self.ar(response, 200)
        self.assertTrue(set(d['lab']) == set(self.superuser.lab))

    def test_public_user(self):
        # makes sure the public user can't post
        self.client.login(username='troublemaker', password='azerty')
        self.client.force_login(user=self.public_user)
        response = self.post(reverse('lab-list'), {'name': 'prank'})
        self.ar(response, 403)

    def test_user_rest(self):
        response = self.client.get(reverse('user-list') + '/test')
        self.ar(response, 200)
        response = self.client.get(reverse('user-list') + '/troublemaker')
        self.ar(response, 200)
        self.assertEqual(
            response.data.get('allowed_users'),
            list(self.public_user.allowed_users.all().values_list('username', flat=True))
        )

    def test_note_rest(self):
        user = self.ar(self.client.get(reverse('user-list')), 200)
        from subjects.models import Subject
        sub = Subject.objects.first()
        my_note = {'user': user[0]['username'],
                   'content_type': 'subject',
                   'object_id': sub.pk,
                   'text': "gnagnagna"}
        my_note = self.ar(self.client.post(reverse('note-list'), data=my_note), 201)
        self.assertTrue(my_note['user'] == user[0]['username'])
        self.assertTrue(self.client.delete(reverse('note-detail', args=[my_note['id']])), 204)


class TestCacheView(BaseTests):
    def setUp(self):
        # This doesn't need super user privileges but I didn't know how to create a normal user
        self.superuser = get_user_model().objects.create_user('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.tag = Tag.objects.create(name='2022_Q1_paper')

    def test_cache_version_view(self):
        r = self.client.get(reverse('cache-info', args=['TAG_NAME_2021']), follow=True)
        self.assertEqual(404, r.status_code)
        URL = 'http://example.com'
        with mock.patch('misc.views.requests') as req, mock.patch('misc.views.TABLES_ROOT', URL):
            cache_info = {'date_created': '2022-08-10 13:33', 'min_api_version': '1.13.0'}
            req.get().json.return_value = cache_info
            r = self.client.get(reverse('cache-info'), follow=True)
            self.assertEqual(200, r.status_code)
            self.assertEqual(r.json(), cache_info)

    def test_get_cache_info(self):
        # First test with local file path
        # NB: This test will fail on Windows
        cache_info = {'date_created': '2022-08-10 13:33', 'min_api_version': '1.13.0'}
        with tempfile.TemporaryDirectory() as URI, mock.patch('misc.views.TABLES_ROOT', URI):
            # Test without tag
            with open(URI + '/cache_info.json', 'w') as fp:
                json.dump(cache_info, fp)
            self.assertEqual(_get_cache_info(), cache_info)

            # Test with tag
            cache_info['min_api_version'] = '1.14.0'
            (new_path := Path(URI, self.tag.name)).mkdir()
            with open(new_path / 'cache_info.json', 'w') as fp:
                json.dump(cache_info, fp)
            self.assertEqual(_get_cache_info(self.tag.name), cache_info)

        # Second, test URL
        URL = 'http://example.com/cache'
        with mock.patch('misc.views.requests') as req, mock.patch('misc.views.TABLES_ROOT', URL):
            req.get().json.return_value = cache_info.copy()
            # Test without tag
            returned = _get_cache_info()
            req.get.assert_called_with(URL + '/cache_info.json')
            self.assertEqual(returned.pop('location', None), URL + '/cache.zip')
            self.assertEqual(returned, cache_info)
            # Test with tag
            returned = _get_cache_info(self.tag.name)
            req.get.assert_called_with(f'{URL}/{self.tag.name}/cache_info.json')
            self.assertEqual(returned.pop('location', None), f'{URL}/{self.tag.name}/cache.zip')
            self.assertEqual(returned, cache_info)

        # Third, test S3
        path = 'example-bucket/cache'
        URL = 's3://' + path
        with mock.patch('misc.views.TABLES_ROOT', URL), \
                mock.patch('pyarrow.fs.S3FileSystem') as s3, \
                mock.patch('misc.views.json.load') as json_mock:
            s3().region = 'eu-west-2'
            # Without tag
            json_mock.return_value = cache_info.copy()
            returned = _get_cache_info()
            s3().open_input_stream.assert_called_with(f'{path}/cache_info.json')
            expected = 'https://example-bucket.s3.eu-west-2.amazonaws.com/cache/cache.zip'
            self.assertEqual(expected, returned.pop('location', None))
            self.assertEqual(returned, cache_info)
            # With tag
            returned = _get_cache_info(self.tag.name)
            path += f'/{self.tag.name}'
            s3().open_input_stream.assert_called_with(f'{path}/cache_info.json')
            expected = expected.rsplit('/', 2)[0] + f'/cache/{self.tag.name}/cache.zip'
            self.assertEqual(expected, returned.pop('location', None))
            self.assertEqual(returned, cache_info)

        # Test URI validation
        with mock.patch('misc.views.TABLES_ROOT', 'fs://path/to/cache'), \
                self.assertRaises(ValueError):
            _get_cache_info()


class APIHousingTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.lab = Lab.objects.create(name='housing_lab')
        self.other_lab = Lab.objects.create(name='other_housing_lab')
        make = Subject.objects.create
        self.s1 = make(nickname='hs1', lab=self.lab, responsible_user=self.superuser)
        self.s2 = make(nickname='hs2', lab=self.lab, responsible_user=self.superuser)
        self.s3 = make(nickname='hs3', lab=self.other_lab, responsible_user=self.superuser)
        self.wheel = Enrichment.objects.create(name='hs wheel')
        self.url = reverse('housing-subject-list')
        self.start = '2026-09-30T10:00:00+02:00'

    def _post(self, subjects, cage='HCAGE_01', **kwargs):
        data = {'cage_name': cage, 'subjects': subjects, 'start_datetime': self.start, **kwargs}
        return self.post(self.url, data)

    def test_create_housing_and_assignments(self):
        d = self.ar(self._post(['hs1']), 201)
        self.assertEqual(d['housing']['cage_name'], 'HCAGE_01')
        self.assertEqual(d['housing']['subjects'], ['hs1'])
        self.assertEqual(d['housing']['lab'], 'housing_lab')
        self.assertEqual([x['subject'] for x in d['housing_subjects']], ['hs1'])
        self.assertEqual(Housing.objects.filter(cage_name='HCAGE_01').count(), 1)
        # a second subject joins the same housing, the first assignment is untouched
        d2 = self.ar(self._post(['hs1', 'hs2']), 201)
        self.assertEqual(d2['housing']['id'], d['housing']['id'])
        self.assertEqual(d2['housing']['subjects'], ['hs1', 'hs2'])
        self.assertEqual(HousingSubject.objects.filter(subject=self.s1).count(), 1)
        self.assertEqual(HousingSubject.objects.filter(subject=self.s2).count(), 1)

    def test_moving_subject_closes_previous_assignment(self):
        self.ar(self._post(['hs1'], cage='HCAGE_A'), 201)
        d = self.ar(self._post(['hs1'], cage='HCAGE_B'), 201)
        self.assertEqual(d['housing']['subjects'], ['hs1'])
        old = HousingSubject.objects.get(subject=self.s1, housing__cage_name='HCAGE_A')
        self.assertIsNotNone(old.end_datetime)
        self.assertEqual(self.s1.housing_subjects.filter(end_datetime__isnull=True).count(), 1)

    def test_cage_names_are_scoped_by_lab(self):
        a = self.ar(self._post(['hs1']), 201)['housing']['id']
        b = self.ar(self._post(['hs3']), 201)['housing']['id']
        self.assertNotEqual(a, b)
        # subjects of different labs cannot share a cage
        self.ar(self._post(['hs2', 'hs3']), 400)

    def test_changed_conditions_create_new_housing(self):
        first = self.ar(self._post(['hs1'], light_cycle=0), 201)['housing']
        same = self.ar(self._post(['hs2'], light_cycle=0), 201)['housing']
        self.assertEqual(same['id'], first['id'])
        new = self.ar(self._post(['hs1', 'hs2'], enrichment='hs wheel'), 201)['housing']
        self.assertNotEqual(new['id'], first['id'])
        self.assertEqual(new['enrichment'], 'hs wheel')
        self.assertEqual(new['light_cycle'], 0)
        self.assertEqual(new['subjects'], ['hs1', 'hs2'])
        # the old housing is kept as history, without current subjects
        old = Housing.objects.get(pk=first['id'])
        self.assertFalse(old.subjects_current().exists())
        self.assertEqual(Housing.objects.filter(cage_name='HCAGE_01').count(), 2)

    def test_validation(self):
        self.ar(self._post([]), 400)
        self.ar(self._post(['nobody']), 400)
        self.ar(self._post(['hs1', 'hs1']), 400)
        self.ar(self._post(['hs1'], enrichment='unknown'), 400)
        self.ar(self.post(self.url, {'cage_name': 'X', 'subjects': ['hs1']}), 400)
        self.assertFalse(Housing.objects.filter(cage_name__in=['HCAGE_01', 'X']).exists())

    def test_patch_housing_conditions(self):
        h = self.ar(self._post(['hs1']), 201)['housing']
        detail = reverse('housing-detail', kwargs={'pk': h['id']})
        d = self.ar(self.patch(detail, {'enrichment': 'hs wheel'}))
        # history: a new housing holds the subject, the old one has ended
        self.assertNotEqual(d['id'], h['id'])
        self.assertEqual(d['subjects'], ['hs1'])
        self.assertEqual(d['enrichment'], 'hs wheel')
        self.assertEqual(self.ar(self.client.get(detail))['subjects'], [])
        # the cage cannot be renamed, and a historical housing cannot be edited
        new_detail = reverse('housing-detail', kwargs={'pk': d['id']})
        self.ar(self.patch(new_detail, {'cage_name': 'RENAMED'}))
        self.assertEqual(Housing.objects.get(pk=d['id']).cage_name, 'HCAGE_01')
        self.ar(self.patch(detail, {'light_cycle': 1}), 400)

    def test_list_filters(self):
        self.ar(self._post(['hs1'], cage='HCAGE_A'), 201)
        self.ar(self._post(['hs1'], cage='HCAGE_B'), 201)
        self.ar(self._post(['hs3'], cage='HCAGE_A'), 201)
        housings = self.ar(self.client.get(reverse('housing-list') + '?subject=hs1'))
        self.assertEqual(sorted(h['cage_name'] for h in housings), ['HCAGE_A', 'HCAGE_B'])
        current = self.ar(self.client.get(reverse('housing-list') + '?subject=hs1&current=true'))
        self.assertEqual([h['cage_name'] for h in current], ['HCAGE_B'])
        lab = self.ar(self.client.get(reverse('housing-list') + '?cage_name=HCAGE_A&lab=other_housing_lab'))
        self.assertEqual([h['subjects'] for h in lab], [['hs3']])
        subs = self.ar(self.client.get(self.url + '?subject=hs1'))
        self.assertEqual(len(subs), 2)
        self.assertEqual([s['cage_name'] for s in subs if s['end_datetime'] is None], ['HCAGE_B'])
        subs = self.ar(self.client.get(self.url + '?cage_name=HCAGE_A&current=true'))
        self.assertEqual([s['subject'] for s in subs], ['hs3'])
