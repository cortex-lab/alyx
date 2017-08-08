from django.contrib.auth.models import User
from django.urls import reverse

from alyx.base import BaseTests


class APIDataTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

        # Create some static data.
        self.client.post(reverse('datarepositorytype-list'), {'name': 'drt'})
        self.client.post(reverse('datarepository-list'), {'name': 'dr'})
        self.client.post(reverse('datasettype-list'), {'name': 'dst'})

    def test_datarepositorytype_list(self):
        r = self.client.get(reverse('datarepositorytype-list'))
        self.ar(r)
        self.assertEqual(r.data[0]['name'], 'drt')

    def test_datarepository_list(self):
        r = self.client.get(reverse('datarepository-list'))
        self.ar(r)
        self.assertEqual(r.data[0]['name'], 'dr')

    def test_datasettype_list(self):
        r = self.client.get(reverse('datasettype-list'))
        self.ar(r)
        self.assertEqual(r.data[0]['name'], 'dst')

    def test_dataset_filerecord(self):
        # Create a dataset.
        data = {'name': 'mydataset',
                'dataset_type': 'dst',
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
