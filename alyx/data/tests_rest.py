import datetime
import os.path as op
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse

from alyx.base import BaseTests
from data.models import Dataset, FileRecord, Download


class APIDataTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

        # Create some static data.
        self.post(reverse('datarepositorytype-list'), {'name': 'drt'})
        self.post(reverse('datarepository-list'), {'name': 'dr', 'hostname': 'hostname'})
        self.post(reverse('datasettype-list'), {'name': 'dst', 'filename_pattern': '--'})
        self.post(reverse('dataformat-list'), {'name': 'df', 'file_extension': '.-'})
        self.post(reverse('dataformat-list'), {'name': 'e1', 'file_extension': '.e1'})
        self.post(reverse('dataformat-list'), {'name': 'e2', 'file_extension': '.e2'})
        self.subject = self.ar(self.client.get(reverse('subject-list')))[0]['nickname']

        # create some more dataset types a.a, a.b, a.c, a.d etc...
        for let in 'abcd':
            self.post(
                reverse('datasettype-list'),
                {'name': 'a.' + let, 'filename_pattern': 'a.' + let + '.*'})

        # Create a session and base session.
        date = '2018-01-01T12:00'
        r = self.client.post(
            reverse('session-list'),
            data={'subject': self.subject, 'start_time': date})
        self.ar(r, 201)

        url = r.data['url']
        self.ar(self.client.post(
            reverse('session-list'),
            {'subject': self.subject, 'start_time': date, 'number': 2,
             'parent_session': url}), 201)

    def test_datarepositorytype(self):
        r = self.client.get(reverse('datarepositorytype-list'))
        self.assertEqual(self.ar(r)[0]['name'], 'drt')

        r = self.client.get(reverse('datarepositorytype-detail', kwargs={'name': 'drt'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'drt')

    def test_datarepository(self):
        r = self.client.get(reverse('datarepository-list'))
        self.assertEqual(self.ar(r)[-1]['name'], 'dr')

        r = self.client.get(reverse('datarepository-detail', kwargs={'name': 'dr'}))
        self.assertEqual(self.ar(r)['name'], 'dr')

    def test_datasettype(self):
        r = self.client.get(reverse('datasettype-list'))
        d = next((_ for _ in self.ar(r) if _['name'] == 'dst'), None)
        self.assertTrue(d is not None)
        self.assertEqual(d['name'], 'dst')

        r = self.client.get(reverse('datasettype-detail', kwargs={'name': 'dst'}))
        self.ar(r)
        self.assertEqual(r.data['name'], 'dst')

    def test_dataformat(self):
        r = self.client.get(reverse('dataformat-list'))
        data = self.ar(r)
        d = next((_ for _ in data if _['name'] == 'df'), None)
        self.assertTrue(d is not None)
        self.assertEqual(d['name'], 'df')

        r = self.client.get(reverse('dataformat-detail', kwargs={'name': 'df'}))
        data = self.ar(r)
        self.assertEqual(data['name'], 'df')

    def test_dataset_filerecord(self):
        # Create a dataset.
        data = {'name': 'mydataset',
                'dataset_type': 'dst',
                'data_format': 'df',
                'file_size': 1234,
                }
        r = self.post(reverse('dataset-list'), data)
        self.ar(r, 201)
        r = self.client.get(reverse('dataset-list'))
        rdata = self.ar(r)[0]
        self.assertTrue(rdata['url'] is not None)
        # Test using the returned URL.
        self.assertEqual(self.ar(self.client.get(rdata['url']))['name'], 'mydataset')
        self.assertTrue(rdata['created_datetime'] is not None)
        self.assertEqual(rdata['name'], 'mydataset')
        self.assertEqual(rdata['file_size'], 1234)
        self.assertEqual(rdata['dataset_type'], 'dst')
        self.assertEqual(rdata['created_by'], 'test')

        # Create a file record.
        dataset = rdata['url']
        data = {'dataset': dataset,
                'data_repository': 'dr',
                'relative_path': 'path/to/file',
                }
        r = self.post(reverse('filerecord-list'), data)
        self.ar(r, 201)

        rdata = self.ar(self.client.get(reverse('filerecord-list')))[0]
        self.assertTrue(rdata['url'] is not None)
        # Test using the returned URL.
        self.assertEqual(self.client.get(rdata['url']).data['relative_path'], 'path/to/file')
        self.assertEqual(rdata['dataset'], dataset)
        self.assertEqual(rdata['data_repository'], 'dr')
        self.assertEqual(rdata['relative_path'], 'path/to/file')

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
        r = self.post(reverse('dataset-list'), data)
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
        data[1]['created_datetime'] = '2018-02-21T12:00'
        data[1]['name'] = 'dataset-created-after'
        r = self.post(reverse('dataset-list'), data[0])
        self.ar(r, 201)
        r = self.post(reverse('dataset-list'), data[1])
        self.ar(r, 201)
        # only one has been created before 2018-01-01
        r = self.client.get(reverse('dataset-list') + '?created_date_lte=2018-01-01')
        a = [datetime.datetime.strptime(d['created_datetime'],
                                        '%Y-%m-%dT%H:%M:%S') for d in self.ar(r)]
        self.assertTrue(max(a).date() <= datetime.date(2018, 1, 1))
        # only one has been created on 2018-02-21
        r = self.client.get(reverse('dataset-list') + '?created_date=2018-02-21')
        res = self.ar(r, 200)
        self.assertTrue(res[0]['name'] == 'dataset-created-after')
        self.assertTrue(len(res) == 1)
        # but both correspond to session of 2018-01-01
        r = self.client.get(reverse('dataset-list') + '?date=2018-01-01')
        self.assertTrue(len(self.ar(r, 200)) == 2)

    def test_register_files(self):
        # create 4 repositories, 2 per lab
        self.post(reverse('datarepository-list'), {'name': 'dra1', 'hostname': 'hosta1'})
        self.post(reverse('datarepository-list'), {'name': 'dra2', 'hostname': 'hosta2'})
        self.post(reverse('datarepository-list'), {'name': 'drb1', 'hostname': 'hostb1'})
        self.post(reverse('datarepository-list'), {'name': 'drb2', 'hostname': 'hostb2'})

        self.post(reverse('lab-list'), {'name': 'laba', 'repositories': ['dra1', 'dra2']})
        self.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb1', 'drb2']})

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
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.b.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)

        # re-register the same dataset, check that there is only one
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self.assertTrue(Dataset.objects.filter(name='a.b.e1').count() == 1)
        # re-register the same dataset with a different collection throws an error
        data['filenames'] = 'alf/titi/a.b.e1'
        # re-register a dataset with the same name but a different subcollection adds a new dataset
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self.assertTrue(Dataset.objects.filter(name='a.b.e1').count() == 2)
        # but registering a dataset using a subollection that matches another raises an error
        data['path'] = '%s/2018-01-01/002' % self.subject
        data['filenames'] = 'dir/a.b.e1'
        # the dataset already exists and results in a 500 integrity error
        self.ar(self.post(reverse('register-file'), data), 500)

    def test_register_files_hostname(self):
        # this is old use case where we register one dataset according to the hostname, no need
        # for a lab in this case. NB the reverse doesn't work with lists while the true endpoint
        # does
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'hostname': 'hostname',
                'hashes': '71f920fa275127a7b60fa4d4d41432a3,71f920fa275127a7b60fa4d4d41432a1',
                'filesizes': '14564,45686',
                'versions': '1.1.1,2.2.2',
                }
        r = self.post(reverse('register-file'), data)
        self.ar(r, 201)
        self._assert_registration(r, data)
        ds0 = Dataset.objects.get(name='a.b.e1')
        ds1 = Dataset.objects.get(name='a.c.e2')
        self.assertEqual(uuid.UUID(ds0.hash), uuid.UUID('71f920fa275127a7b60fa4d4d41432a3'))
        self.assertEqual(uuid.UUID(ds1.hash), uuid.UUID('71f920fa275127a7b60fa4d4d41432a1'))
        self.assertEqual(ds0.file_size, 14564)
        self.assertEqual(ds1.file_size, 45686)
        self.assertEqual(ds0.version, '1.1.1')
        self.assertEqual(ds1.version, '2.2.2')

    def test_register_files_hash(self):
        # this is old use case where we register one dataset according to the hostname, no need
        # for a lab in this case
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'name': 'dr',
                }
        r = self.post(reverse('register-file'), data)
        self.ar(r, 201)
        self._assert_registration(r, data)

    def test_register_files_reponame(self):
        # this is old use case where we register one dataset according to the hostname, no need
        # for a lab in this case
        data = {'path': '%s/2018-01-01/2/dir' % self.subject,
                'filenames': 'a.b.e1,a.c.e2',
                'name': 'dr',
                }
        r = self.post(reverse('register-file'), data)
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
            r = self.post(reverse('dataset-list'), data)
            self.ar(r, 201)
            pks.append(r.data['url'][r.data['url'].rindex('/') + 1:])

        # 3 downloads of the same dataset with the same user (the count should increase).
        dpks = []
        pk = pks[0]
        for i in range(3):
            r = self.post(reverse('new-download'), {
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
        r = self.post(reverse('new-download'), {
            'user': 'test',
            'datasets': pk,
            'projects': 'tp1,tp2',
        })
        self.ar(r, 201)
        self.assertTrue(r.data['count'][0] == 4)
        d = Download.objects.last()
        self.assertEqual([p.name for p in d.projects.all()], ['tp1', 'tp2'])

        # test with several datasets
        r = self.post(reverse('new-download'), {
            'user': 'test',
            'datasets': ','.join(pks),
            'projects': 'tp3',
        })
        self.assertEqual(len(r.data['download']), 3)
        self.assertEqual(Download.objects.filter(projects__name='tp3').count(), 3)
