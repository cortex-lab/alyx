from datetime import datetime
from unittest import mock
from pathlib import Path
import json
import tempfile

from django.urls import reverse
from django.contrib.auth import get_user_model

from alyx.base import BaseTests
from misc.models import LabMembership, Lab
from misc.views import _get_cache_info
from data.models import Tag


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.lab = Lab.objects.create(name='basement')
        self.public_user = get_user_model().objects.create(
            username='troublemaker', password='azerty', is_public_user=True)

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
        # This doesn't need super user privilages but I didn't know how to create a normal user
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
