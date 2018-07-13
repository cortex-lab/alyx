import datetime
import os.path as op

from django.contrib.auth import get_user_model
from django.urls import reverse

from alyx.base import BaseTests


class APIDataTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

        # Create some static data.
        self.client.post(reverse('datarepositorytype-list'), {'name': 'drt'})
        self.client.post(reverse('datarepository-list'), {'name': 'dr', 'dns': 'dns'})
        self.client.post(reverse('datasettype-list'), {'name': 'dst', 'filename_pattern': '--'})
        self.client.post(reverse('dataformat-list'), {'name': 'df', 'file_extension': '.-'})

        self.subject = self.client.get(reverse('subject-list')).data[0]['nickname']

        # Create a session and base session.
        date = '2018-01-01T12:00'
        r = self.client.post(
            reverse('session-list'),
            {'subject': self.subject, 'start_time': date})

        url = r.data['url']
        r = self.client.post(
            reverse('session-list'),
            {'subject': self.subject, 'start_time': date, 'number': 2, 'parent_session': url})

    def test_datarepositorytype(self):
        r = self.client.get(reverse('datarepositorytype-list'))
        self.ar(r)
        self.assertEqual(r.data[0]['name'], 'drt')

        r = self.client.get(reverse('datarepositorytype-detail', kwargs={'name': 'drt'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'drt')

    def test_datarepository(self):
        r = self.client.get(reverse('datarepository-list'))
        self.ar(r)
        self.assertEqual(r.data[-1]['name'], 'dr')

        r = self.client.get(reverse('datarepository-detail', kwargs={'name': 'dr'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'dr')

    def test_datasettype(self):
        r = self.client.get(reverse('datasettype-list'))
        self.ar(r)
        d = next((_ for _ in r.data if _['name'] == 'dst'), None)
        self.assertTrue(d is not None)
        self.assertEqual(d['name'], 'dst')

        r = self.client.get(reverse('datasettype-detail', kwargs={'name': 'dst'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'dst')

    def test_dataformat(self):
        r = self.client.get(reverse('dataformat-list'))
        self.ar(r)
        d = next((_ for _ in r.data if _['name'] == 'df'), None)
        self.assertTrue(d is not None)
        self.assertEqual(d['name'], 'df')

        r = self.client.get(reverse('dataformat-detail', kwargs={'name': 'df'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'df')

    def test_dataset_filerecord(self):
        # Create a dataset.
        data = {'name': 'mydataset',
                'dataset_type': 'dst',
                'data_format': 'df',
                }
        r = self.client.post(reverse('dataset-list'), data)
        self.ar(r, 201)

        r = self.client.get(reverse('dataset-list'))
        self.ar(r)
        self.assertTrue(r.data[0]['url'] is not None)
        # Test using the returned URL.
        self.assertEqual(self.client.get(r.data[0]['url']).data['name'], 'mydataset')
        self.assertTrue(r.data[0]['created_datetime'] is not None)
        self.assertEqual(r.data[0]['name'], 'mydataset')
        self.assertEqual(r.data[0]['dataset_type'], 'dst')
        self.assertEqual(r.data[0]['created_by'], 'test')

        # Create a file record.
        dataset = r.data[0]['url']
        data = {'dataset': dataset,
                'data_repository': 'dr',
                'relative_path': 'path/to/file',
                }
        r = self.client.post(reverse('filerecord-list'), data)
        self.ar(r, 201)

        r = self.client.get(reverse('filerecord-list'))
        self.ar(r)
        self.assertTrue(r.data[0]['url'] is not None)
        # Test using the returned URL.
        self.assertEqual(self.client.get(r.data[0]['url']).data['relative_path'], 'path/to/file')
        self.assertEqual(r.data[0]['dataset'], dataset)
        self.assertEqual(r.data[0]['data_repository'], 'dr')
        self.assertEqual(r.data[0]['relative_path'], 'path/to/file')

    def test_dataset(self):
        data = {
            'name': 'some-dataset',
            'dataset_type': 'dst',
            'created_by': 'test',
            'subject': self.subject,
            #'dataset_type': 'dst',
            'data_format': 'df',
            'date': '2018-01-01',
            'number': 2,
        }
        # Post the dataset.
        r = self.client.post(reverse('dataset-list'), data)
        self.ar(r, 201)
        # Make sure a session has been created.
        session = r.data['session']
        r = self.client.get(session)
        self.ar(r, 200)
        self.assertEqual(r.data['subject'], self.subject)
        self.assertEqual(r.data['start_time'][:10], data['date'])

    def test_dataset_date_filter(self):
        # create 2 datasets with different dates
        data = {
            'name': 'some-filter-dataset',
            'dataset_type': 'dst',
            'created_by': 'test',
            'subject': self.subject,
            'data_format': 'df',
            'date': '2018-01-01',
            'created_datetime': '2018-01-01T12:34',
            'number': 2,
        }
        data = [data, data.copy()]
        data[1]['created_datetime'] = '2017-12-21T12:00'
        r = self.client.post(reverse('dataset-list'), data[0])
        self.ar(r, 201)
        r = self.client.post(reverse('dataset-list'), data[1])
        self.ar(r, 201)
        r = self.client.get(reverse('dataset-list') + '?created_datetime_lte=2018-01-01')
        a = [datetime.datetime.strptime(d['created_datetime'],
                                        '%Y-%m-%dT%H:%M:%S') for d in r.data]
        self.assertTrue(max(a) <= datetime.datetime(2018, 1, 1))

    def test_register_files(self):
        self.client.post(reverse('project-list'), {'name': 'tp', 'repositories': ['dr']})

        self.client.post(
            reverse('datasettype-list'),
            {'name': 'a.b', 'filename_pattern': 'a.b.*'})

        self.client.post(
            reverse('datasettype-list'),
            {'name': 'a.c', 'filename_pattern': 'a.c.*'})

        self.client.post(reverse('dataformat-list'), {'name': 'e1', 'file_extension': '.e1'})
        self.client.post(reverse('dataformat-list'), {'name': 'e2', 'file_extension': '.e2'})

        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'dns': 'dns',
                'projects': 'tp',
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)

        d0, d1 = r.data

        self.assertEqual(d0['name'], 'a.b.e1')
        self.assertEqual(d0['created_by'], 'test')
        self.assertEqual(d0['dataset_type'], 'a.b')
        self.assertEqual(d0['data_format'], 'e1')

        self.assertEqual(d1['name'], 'a.c.e2')
        self.assertEqual(d1['created_by'], 'test')
        self.assertEqual(d1['dataset_type'], 'a.c')
        self.assertEqual(d1['data_format'], 'e2')

        self.assertEqual(d0['file_records'][0]['data_repository'], 'dr')
        self.assertEqual(d0['file_records'][0]['relative_path'],
                         op.join(data['path'], 'a.b.e1'))

        self.assertEqual(d1['file_records'][0]['data_repository'], 'dr')
        self.assertEqual(d1['file_records'][0]['relative_path'],
                         op.join(data['path'], 'a.c.e2'))
