import datetime
import os.path as op
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse

from alyx.base import BaseTests
from data.models import Dataset, FileRecord, Download, Tag


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
        self.post(reverse('revision-list'), {'name': 'v1', 'collection': 'v1'})

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
        mod_date = rdata['auto_datetime']

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

        # Test that the modified datetime field of dataset is updated when filerecord saved/created
        new_mod_date = self.client.get(dataset).data['auto_datetime']
        self.assertTrue(new_mod_date > mod_date)

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
        # Check collection and revision have been set to default values
        self.assertEqual(r.data['revision'], None)
        self.assertEqual(r.data['collection'], None)
        # Check that it has been set as the default dataset
        self.assertEqual(r.data['default_dataset'], True)
        # Make sure a session has been created.
        session = r.data['session']
        r = self.client.get(session)
        self.ar(r, 200)
        self.assertEqual(r.data['subject'], self.subject)
        self.assertEqual(r.data['start_time'][:10], data['date'])

        # Create dataset with collection and revision specified
        data = {
            'name': 'some-dataset',
            'dataset_type': 'dst',
            'created_by': 'test',
            'subject': self.subject,
            'data_format': 'df',
            'date': '2018-01-01',
            'number': 2,
            'collection': 'test_path',
        }

        r = self.post(reverse('dataset-list'), data)
        self.ar(r, 201)
        self.assertEqual(r.data['revision'], None)
        self.assertEqual(r.data['collection'], data['collection'])
        self.assertEqual(r.data['default_dataset'], True)
        data_url = r.data['url']

        # But if we change the collection, we are okay
        data['revision'] = 'v1'
        r = self.post(reverse('dataset-list'), data)
        self.ar(r, 201)
        self.assertEqual(r.data['revision'], data['revision'])
        self.assertEqual(r.data['collection'], data['collection'])
        self.assertEqual(r.data['default_dataset'], True)

        # Get the previous dataset and make sure this is no longer the default one
        r = self.ar(self.client.get(data_url))
        self.assertEqual(r['default_dataset'], False)

        # Make sure if you specify the default dataset flag to false it is indeed false
        data['collection'] = None
        data['default_dataset'] = False
        r = self.post(reverse('dataset-list'), data)
        self.ar(r, 201)
        self.assertEqual(r.data['default_dataset'], False)

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
        r = self.client.get(reverse('dataset-list') + '?created_date_lte=2018-01-01T12:00')
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
        self.assertEqual(1, Dataset.objects.filter(name='a.b.e1').count())
        # re-register a dataset with the same name but a different
        # sub-collection adds a new dataset
        data['filenames'] = 'alf/titi/a.b.e1'
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self.assertEqual(2, Dataset.objects.filter(name='a.b.e1').count())
        # behaviour is the same regardless of whether collection is in path or filenames field
        data['path'] = '%s/2018-01-01/002' % self.subject
        data['filenames'] = 'dir/a.b.e1'
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 201)
        self.assertTrue(Dataset.objects.filter(name='a.b.e1').count() == 2)  # No new datasets
        # NB: This used to result in a different behaviour...
        # but registering a dataset using a sub-collection that matches another raises an error
        # the dataset already exists and results in a 500 integrity error
        # self.ar(self.post(reverse('register-file'), data), 500)

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

    def test_register_existence_options(self):

        self.post(reverse('datarepository-list'), {'name': 'ibl1', 'hostname': 'iblhost1',
                                                   'globus_is_personal': 'True'})
        self.post(reverse('datarepository-list'), {'name': 'ibl2', 'hostname': 'iblhost2',
                                                   'globus_is_personal': 'True'})
        # server repo
        self.post(reverse('datarepository-list'), {'name': 'ibl3', 'hostname': 'iblhost3',
                                                   'globus_is_personal': 'False'})

        self.post(reverse('lab-list'), {'name': 'ibl',
                                        'repositories': ['ibl1', 'ibl2', 'ibl3']})

        # Case 1, server_only = False, no repo name specified
        # Expect: 3 file records (one for each repo),
        # all with exists = False (preserves old behavior)
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.a.e1',  # this is the repository name
                'server_only': False,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 3)
        for fr in frs:
            self.assertEqual(fr['exists'], False)

        # Case 2, server_only = True, no repo name specified
        # Expect: 1 file record for data repo with globus is personal == True,
        # with exists = True (preserves old behavior)

        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.a.e2',  # this is the repository name
                'server_only': True,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 1)
        self.assertEqual(frs[0]['exists'], True)
        self.assertEqual(frs[0]['data_repository'], 'ibl3')

        # Case 3, server_only = False, repo name specified
        # Expect: 3 file records, specified repo with exists = True,
        # the others False (preserves old behavior)
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.b.e1',  # this is the repository name
                'name': 'ibl1',
                'server_only': False,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 3)
        for fr in frs:
            self.assertEqual(fr['exists'], fr['data_repository'] == 'ibl1')

        # Case 4, server_only = False, repo name specified, exists = False
        # Expect: 3 file records, all with exists = False
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.b.e2',  # this is the repository name
                'name': 'ibl1',
                'server_only': False,
                'exists': False,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 3)
        for fr in frs:
            self.assertEqual(fr['exists'], False)

        # Case 5, server_only = True, repo name specified
        # Expect: 2 file records, 1 for specified repo and 1 for server repo,
        # all with exists = True (preserves old behavior)
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.c.e1',  # this is the repository name
                'name': 'ibl1',
                'server_only': True,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 2)
        for fr in frs:
            self.assertEqual(fr['exists'], True)

        # Case 6, server_only = True, repo name specified, exists = False
        # Expect: 2 file records, 1 for specified repo and 1 for server repo,
        # all with exists = False
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.c.e2',  # this is the repository name
                'name': 'ibl1',
                'server_only': True,
                'exists': False,
                'labs': ['ibl']
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        frs = r['file_records']
        self.assertTrue(len(frs) == 2)
        for fr in frs:
            self.assertEqual(fr['exists'], False)

    def test_register_with_revision(self):
        self.post(reverse('datarepository-list'), {'name': 'drb2', 'hostname': 'hostb2'})
        self.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb2']})

        # First test that adding no revision gives None
        # No collection, no revision
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]

        self.assertTrue(not r['revision'])
        self.assertEqual(r['collection'], 'dir')
        # Check the revision relative path doesn't exist
        self.assertTrue(r['file_records'][0]['relative_path'] ==
                        op.join(data['path'], data['filenames']))

        # Now test specifying a revision in path
        data = {'path': '%s/2018-01-01/002/dir/#v1#' % self.subject,
                'filenames': 'a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]

        self.assertTrue(r['revision'] == 'v1')
        self.assertEqual('dir', r['collection'])
        # Check file record relative path includes revision
        self.assertTrue('#v1#' in r['file_records'][0]['relative_path'])

        # Now test specifying a collection and a revision in filename
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': 'dir1/#v1#/a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        self.assertTrue(r['revision'] == 'v1')
        self.assertTrue(r['collection'] == 'dir/dir1')
        # Check file record relative path includes revision
        self.assertTrue('#v1#' in r['file_records'][0]['relative_path'])

        # Test that giving nested revision folders gives out an error
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': '#dir1#/#v2#/a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 400)

        # Test that giving revision containing collection gives out an error
        data = {'path': '%s/2018-01-01/002/dir' % self.subject,
                'filenames': '#v2#/dir1/a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 400)

        # Test specifying multiple revisions at once
        # Should add an extra revision
        data = {'path': '%s/2018-01-01/002' % self.subject,
                'filenames': 'dir2/#v1#/a.d.e1,#v2#/a.c.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)
        self.assertTrue(r[0]['revision'] == 'v1')
        self.assertTrue(r[1]['revision'] == 'v2')
        self.assertTrue(r[0]['collection'] == 'dir2')
        self.assertTrue(not r[1]['collection'])
        # Check file record relative path includes revision
        self.assertTrue('#v1#' in r[0]['file_records'][0]['relative_path'])
        self.assertTrue('#v2#' in r[1]['file_records'][0]['relative_path'])

        # Check error status with multiple revision folders
        data = {
            'path': '%s/2018-01-01/002/#v1#' % self.subject,
            'filenames': '#v2#/a.d.e1',
            'name': 'drb2',  # this is the repository name
        }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 400)
        # Check error status with subdirectories within revision folder
        data = {'path': '%s/2018-01-01/002/dir2' % self.subject,
                'filenames': '#v1#/alf/a.d.e1',
                'name': 'drb2',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        self.ar(r, 400)

    def test_register_with_tags(self):
        self.post(reverse('datarepository-list'), {'name': 'drb1', 'hostname': 'hostb1'})
        self.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb1']})

        # Create two tags, one that is protected (can't be overwritten) and one not
        self.client.post(reverse('tag-list'), {'name': 'tag1', 'protected': False})
        self.client.post(reverse('tag-list'), {'name': 'tag2', 'protected': True})

        # Create some datasets
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test/v1/a.d.e2,test/v1/a.d.e1,',
                'name': 'drb1',  # this is the repository name
                'filesizes': '14564,24564'
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)
        self.assertEqual(r[0]['file_size'], int(data['filesizes'].split(',')[0]))
        self.assertEqual(r[1]['file_size'], int(data['filesizes'].split(',')[1]))

        # Add the unprotected tag to both datasets
        dataset1 = Dataset.objects.get(pk=r[0]['id'])
        dataset2 = Dataset.objects.get(pk=r[1]['id'])
        tag1 = Tag.objects.get(name='tag1')
        tag2 = Tag.objects.get(name='tag2')
        dataset1.tags.add(tag1)
        dataset2.tags.add(tag1)

        # Change the filesize of datasets, re-register and check that the dataset filesize have
        # been updated
        data['filesizes'] = '20000,30000'
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)
        self.assertEqual(r[0]['file_size'], int(data['filesizes'].split(',')[0]))
        self.assertEqual(r[1]['file_size'], int(data['filesizes'].split(',')[1]))

        # Add protected tag to just the second dataset
        dataset2.tags.add(tag2)

        # Check that we get an error if we register a file that is protected
        data['filesizes'] = '22456,40506'
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 403)

    def test_register_default_dataset(self):
        self.post(reverse('datarepository-list'), {'name': 'drb1', 'hostname': 'hostb1'})
        self.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb1']})

        # Create a dataset and explicitly set default to True
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_default/#v1#/a.d.e2',
                'name': 'drb1',  # this is the repository name
                'default': True
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        dataset_id1 = r['id']
        self.assertEqual(r['default'], True)

        # Create same dataset with no revision and don't explicitly set default to True
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_default/a.d.e2',
                'name': 'drb1',  # this is the repository name
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        dataset_id2 = r['id']
        self.assertEqual(r['default'], True)

        # Check that the previous dataset has it's default status set to false
        r = self.ar(self.client.get(reverse('dataset-list') + '?id=' + str(dataset_id1)))[0]
        self.assertEqual(r['default_dataset'], False)

        # If we update again make sure roles are reversed
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_default/#v1#/a.d.e2',
                'name': 'drb1',  # this is the repository name
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        self.assertEqual(r['default'], True)
        # Also make sure it is the same dataset as before
        self.assertEqual(r['id'], dataset_id1)
        # Check the other revision has correctly been changed
        r = self.ar(self.client.get(reverse('dataset-list') + '?id=' + str(dataset_id2)))[0]
        self.assertEqual(r['default_dataset'], False)

        # Now check that if we register with false, this is correctly set
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_default/a.d.e2',
                'name': 'drb1',  # this is the repository name
                'default': False
                }
        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)[0]
        self.assertEqual(r['default'], False)
        r = self.ar(self.client.get(reverse('dataset-list') + '?id=' + str(dataset_id1)))[0]
        self.assertEqual(r['default_dataset'], True)

    def test_protected_view(self):
        self.post(reverse('datarepository-list'), {'name': 'drb1', 'hostname': 'hostb1'})
        self.post(reverse('lab-list'), {'name': 'labb', 'repositories': ['drb1']})

        # Create protected tag
        self.client.post(reverse('tag-list'), {'name': 'tag1', 'protected': True})

        # Create some datasets and register
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_prot/a.d.e2,test_prot/a.d.e1,',
                'name': 'drb1',  # this is the repository name
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 201)

        # add protected tag to the first dataset
        dataset1 = Dataset.objects.get(pk=r[0]['id'])
        tag1 = Tag.objects.get(name='tag1')
        dataset1.tags.add(tag1)

        # Check the protected status of three files
        # 1. already created + protected --> expect protected=True
        # 2. already created --> expect protected=False
        # 3. not yet created --> expect protected=False
        data = {'path': '%s/2018-01-01/002/' % self.subject,
                'filenames': 'test_prot/a.d.e2,test_prot/a.d.e1,test_prot/a.b.e1',
                'name': 'drb1',
                'check_protected': True
                }

        r = self.client.post(reverse('register-file'), data)
        r = self.ar(r, 403)
        self.assertEqual(r['error'], 'One or more datasets is protected')

        r = r['details']
        (name, prot_info), = r[0].items()
        self.assertEqual(name, 'test_prot/a.d.e2')
        self.assertEqual(prot_info, [{'': True}])
        (name, prot_info), = r[1].items()
        self.assertEqual(name, 'test_prot/a.d.e1')
        self.assertEqual(prot_info, [{'': False}])
        (name, prot_info), = r[2].items()
        self.assertEqual(name, 'test_prot/a.b.e1')
        self.assertEqual(prot_info, [])

    def test_revisions(self):
        # Check revision lookup with name
        self.post(reverse('revision-list'), {'name': 'v2'})
        r = self.client.get(reverse('revision-detail', args=['v2']))
        self.assertEqual(r.data['name'], 'v2')
        r = self.client.get(reverse('revision-detail', args=['foobar']))
        self.ar(r, 404)

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

    def test_auto_datetime_field(self):
        # make a couple of datasets
        mod_dates = []
        dset_urls = []
        for name in ['dset1', 'dset2']:
            data = {'name': name,
                    'dataset_type': 'dst',
                    'data_format': 'df',
                    'file_size': 1234,
                    }
            r = self.post(reverse('dataset-list'), data)
            self.ar(r, 201)
            dset_urls.append(r.data['url'])
            mod_dates.append(r.data['auto_datetime'])

        # update filesize field of the datasets
        dsets = Dataset.objects.filter(name__icontains='dset')
        dsets.update(file_size=2345)

        # Check that in updating the filesize we also updated the modified_datetime field
        for iurl, url in enumerate(dset_urls):
            self.assertTrue(self.client.get(url).data['auto_datetime'] > mod_dates[iurl])

        # set modified datetime to a specific value
        dsets = Dataset.objects.filter(name__icontains='dset')
        dsets.update(file_size=1234, auto_datetime=mod_dates[0])

        # check that all modified_datetime fields are set to the value we chose
        for iurl, url in enumerate(dset_urls):
            self.assertEqual(self.client.get(url).data['auto_datetime'], mod_dates[0])
