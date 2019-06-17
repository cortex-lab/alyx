import datetime
import os.path as op

from django.contrib.auth import get_user_model
from django.urls import reverse

from alyx.base import BaseTests
from data.models import Dataset, FileRecord, Download


class APIDataTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

        # Create some static data.
        self.client.post(reverse('datarepositorytype-list'), {'name': 'drt'})
        self.client.post(reverse('datarepository-list'), {'name': 'dr', 'hostname': 'hostname'})
        self.client.post(reverse('datasettype-list'), {'name': 'dst', 'filename_pattern': '--'})
        self.client.post(reverse('dataformat-list'), {'name': 'df', 'file_extension': '.-'})
        self.client.post(reverse('dataformat-list'), {'name': 'e1', 'file_extension': '.e1'})
        self.client.post(reverse('dataformat-list'), {'name': 'e2', 'file_extension': '.e2'})
        self.subject = self.client.get(reverse('subject-list')).data[0]['nickname']

        # create some more dataset types a.a, a.b, a.c, a.d etc...
        for let in 'abcd':
            self.client.post(
                reverse('datasettype-list'),
                {'name': 'a.' + let, 'filename_pattern': 'a.' + let + '.*'})

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
                'file_size': 1234,
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
        self.assertEqual(r.data[0]['file_size'], 1234)
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
        # create 4 repositories, 2 per lab
        self.client.post(reverse('datarepository-list'), {'name': 'dra1', 'hostname': 'hosta1'})
        self.client.post(reverse('datarepository-list'), {'name': 'dra2', 'hostname': 'hosta2'})
        self.client.post(reverse('datarepository-list'), {'name': 'drb1', 'hostname': 'hostb1'})
        self.client.post(reverse('datarepository-list'), {'name': 'drb2', 'hostname': 'hostb2'})

        self.client.post(reverse('lab-list'), {'name': 'laba', 'repositories': ['dra1', 'dra2']})
        self.client.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb1', 'drb2']})

        # start with registering 2 datasets on lab a, since the repo is not whithin the lab repos
        # we expect 3 file records to be created, do it twice: list and char to test format
        # and also test no duplication on several registrations
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.a.e1,a.b.e1',
                'hostname': 'hostname',
                'labs': ['laba'],
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        fr = FileRecord.objects.filter(dataset=Dataset.objects.get(name='a.a.e1'))
        self.assertTrue(fr.count() == 3)
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        fr = FileRecord.objects.filter(dataset=Dataset.objects.get(name='a.a.e1'))
        self.assertTrue(fr.count() == 3)

        # next test case where a dataset is registered normally first, but is subsequently added
        # to another repository.
        # at first we expect 2 repositories
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.c.e1',
                'name': 'drb1',  # this is the repository name
                'labs': ['labb'],
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        fr = FileRecord.objects.filter(dataset=Dataset.objects.get(name='a.c.e1'))
        self.assertTrue(fr.count() == 2)
        # now we re-register the file, adding a repository not belonging to the lab, and expect
        # 3 file records
        data['name'] = 'dr'
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        fr = FileRecord.objects.filter(dataset=Dataset.objects.get(name='a.c.e1'))
        self.assertTrue(fr.count() == 3)

        # test case where a dataset is subsequently registered with a different user
        # doesn't break and the last user is labeled on the dataset
        data['created_by'] = '17'
        r = self.client.post(reverse('register-file'), data)
        self.assertEqual(r.data[0]['created_by'], '17')

        # last use case is about registering a dataset without a lab, the lab should be inferred
        # from the subject
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)

    def test_register_files_hostname(self):
        # this is old use case where we register one dataset according to the hostname, no need
        # for a lab in this case
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'hostname': 'hostname',
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self._assert_registration(r, data)

    def test_register_files_reponame(self):
        # this is old use case where we register one dataset according to the hostname, no need
        # for a lab in this case
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'name': 'dr',
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self._assert_registration(r, data)

    def _assert_registration(self, r, data):
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

    def test_download(self):
        # Create a dataset.
        pks = []
        for name in ['mydataset1', 'mydataset2', 'mydataset3']:
            data = {'name': name,
                    'dataset_type': 'dst',
                    'data_format': 'df',
                    'file_size': 1234,
                    }
            r = self.client.post(reverse('dataset-list'), data)
            self.ar(r, 201)
            pks.append(r.data['url'][r.data['url'].rindex('/') + 1:])

        # 3 downloads of the same dataset with the same user (the count should increase).
        dpks = []
        pk = pks[0]
        for i in range(3):
            r = self.client.post(reverse('new-download'), {
                'user': 'test',
                'datasets': pk,
            })
            self.ar(r, 201)
            dpk = r.data['download']
            assert r.data['count'][0] == i + 1
            assert not dpks or dpk in dpks  # the download PK should be the same

        # Test with projects
        self.ar(self.client.post(reverse('project-list'), {'name': 'tp1'}), 201)
        self.ar(self.client.post(reverse('project-list'), {'name': 'tp2'}), 201)
        self.ar(self.client.post(reverse('project-list'), {'name': 'tp3'}), 201)

        # test with one dataset and several projects, expected count is 4
        r = self.client.post(reverse('new-download'), {
            'user': 'test',
            'datasets': pk,
            'projects': 'tp1,tp2',
        })
        self.ar(r, 201)
        self.assertTrue(r.data['count'][0] == 4)
        d = Download.objects.last()
        self.assertEqual([p.name for p in d.projects.all()], ['tp1', 'tp2'])

        # test with several datasets
        r = self.client.post(reverse('new-download'), {
            'user': 'test',
            'datasets': ','.join(pks),
            'projects': 'tp3',
        })
        self.assertEqual(len(r.data['download']), 3)
        self.assertEqual(Download.objects.filter(projects__name='tp3').count(), 3)
