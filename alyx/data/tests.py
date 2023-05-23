from unittest import mock
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import ProtectedError

from data.management.commands import files
from data.models import Dataset, DatasetType, Tag, Revision, DataRepository, FileRecord
from subjects.models import Subject
from actions.models import Session
from misc.models import Lab
from data.transfers import get_dataset_type


class TestModel(TestCase):
    def test_model_methods(self):
        (dset, _) = Dataset.objects.get_or_create(name='toto.npy')

        self.assertIs(dset.is_online, False)
        self.assertIs(dset.is_public, False)
        self.assertIs(dset.is_protected, False)

    def test_generic_foreign_key(self):
        # Attempt to associate a dataset with a subject
        self.lab = Lab.objects.create(name='test_lab')
        subj = Subject.objects.create(nickname='foo', birth_date='2018-09-01', lab=self.lab)
        dset = Dataset(name='toto.npy', content_object=subj)

        self.assertIs(dset.content_object, subj)

    def test_validation(self):
        # Expect raises when using special characters
        self.assertRaises(ValidationError, Dataset.objects.create,
                          name='toto.npy', collection='~alf/.*')

    def test_delete(self):
        (dset, _) = Dataset.objects.get_or_create(name='foo.npy')
        (tag, _) = Tag.objects.get_or_create(name='protected_tag', protected=True)
        dset.tags.set([tag])
        assert dset.is_protected is True

        # Individual object delete
        with transaction.atomic():
            self.assertRaises(ProtectedError, dset.delete)

        # As queryset
        qs = Dataset.objects.filter(tags__name='protected_tag')
        with transaction.atomic():
            self.assertRaises(ProtectedError, qs.delete)
        with self.assertLogs('data.models', 'WARNING'):
            qs.delete(force=True)


class TestDatasetTypeModel(TestCase):
    def test_model_methods(self):
        dtype, _ = DatasetType.objects.get_or_create(
            name='obj.attr', description='thing', filename_pattern=None)
        dtype2, _ = DatasetType.objects.get_or_create(
            name='foo.bar', description='foo bar', filename_pattern='*FOO.b?r*')
        dtype3, _ = DatasetType.objects.get_or_create(
            name='bar.baz', description='.', filename_pattern=None)
        dtype4, _ = DatasetType.objects.get_or_create(
            name='some_file', description='.', filename_pattern="some_file.*")
        with self.assertRaises(IntegrityError):
            DatasetType.objects.get_or_create(name='objFoo.bar', filename_pattern='*foo.b?r*')
        with self.assertRaises(IntegrityError):
            DatasetType.objects.get_or_create(name='obj.attr', filename_pattern='-')
        filename_typename = (
            ('foo.bar.npy', 'foo.bar'),
            ('foo.bir.npy', 'foo.bar'),
            ('_ns_obj.attr_clock.extra.npy', 'obj.attr'),
            ('bar.baz.ext', 'bar.baz'),
            ('some_file.ext', 'some_file')
        )

        dtypes = DatasetType.objects.all()
        for filename, dataname in filename_typename:
            with self.subTest(filename=filename):
                self.assertEqual(get_dataset_type(filename, dtypes).name, dataname)


class TestRevisionModel(TestCase):
    def test_validation(self):
        # Expect raises when using special characters
        self.assertRaises(ValidationError, Revision.objects.create, name='#2022-01-01.#')


class TestManagementFiles(TestCase):
    """Tests for the files management command."""
    def setUp(self) -> None:
        """Create some data repositories and file records to clean up"""
        # Two of these are 'large' datasets that will be removed
        dtypes = ['ephysData.raw.ap', 'imaging.frames', 'foo.bar.baz']
        self.dtypes = [DatasetType.objects.create(name=name) for name in dtypes]
        # Create two labs
        self.labs = [Lab.objects.create(name=f'lab{i}') for i in range(2)]
        # Create four repos
        repo1 = DataRepository.objects.create(
            name='lab0_local0', lab=self.labs[0], globus_is_personal=True,
            globus_endpoint_id=uuid4(), globus_path='/mnt/foo/')
        repo2 = DataRepository.objects.create(
            name='lab0_local1', lab=self.labs[0], globus_is_personal=True,
            globus_endpoint_id=uuid4(), globus_path='/mnt/foo/')
        repo3 = DataRepository.objects.create(
            name='lab1_local', lab=self.labs[1], globus_is_personal=True,
            globus_endpoint_id=uuid4(), globus_path='/mnt/foo/')
        # NB: name must contain 'flatiron'!
        repo_main = DataRepository.objects.create(
            name='flatiron', globus_is_personal=False,
            globus_endpoint_id=uuid4(), globus_path='/mnt/foo/')
        # Create one session per lab
        subj = Subject.objects.create(nickname='subject')
        sessions = [Session.objects.create(subject=subj, number=1, lab=lab) for lab in self.labs]
        # Create datasets and file records
        self.dset_names = ['ephysData.raw.ap.bin', 'imaging.frames.tar.bz2', 'foo.bar.baz']
        self.dsets = []
        for session in sessions:  # for one session in each lab, create one of each dataset
            self.dsets.extend(
                Dataset.objects.create(name=name, session=session,
                                       dataset_type=next(x for x in self.dtypes if x.name in name))
                for name in self.dset_names)

        # Create file record on each lab's local server and main repo
        session = 'subject/2020-01-01/001'
        self.records = []  # All file records
        for d in self.dsets:
            for repo in (repo1, repo2, repo3, repo_main):
                if repo.globus_is_personal is False:
                    rel_path = f'{session}/{self._dataset_uuid_name(d)}'
                elif repo.lab != d.session.lab:
                    continue  # Don't create file record for dataset if session lab different
                else:
                    rel_path = f'{session}/{d.name}'
                self.records.append(
                    FileRecord.objects.create(
                        relative_path=rel_path, exists=True, dataset=d, data_repository=repo)
                )
        self.command = files.Command()
        self.delete_clients = []

    @mock.patch('data.transfers.globus_transfer_client')
    @mock.patch('data.transfers.globus_sdk.DeleteData')
    def test_removelocal(self, delete_data_mock, client_mock):
        """Test for removelocal action."""
        # Delete datasets created before tomorrow
        before_date = (datetime.now() + timedelta(days=1)).date()

        # Mock delete client to return dict-like MagicMock
        delete_data_mock.side_effect = self._new_delete_client
        # Mock globus list method to return list of all datasets (with and without uuid in name)
        dsets = [self._dataset_uuid_name(d) for d in self.dsets] + self.dset_names
        client_mock().operation_ls.return_value = {'DATA': [dict(name=d, size=0) for d in dsets]}

        # First run in dry mode, expect submit_delete to not be called
        self.command.handle(action='removelocal', lab='lab1',
                            before=str(before_date), y=True, dry=True)
        client_mock().operation_ls.assert_called()
        client_mock().submit_delete.assert_not_called()
        # All file records should still exist
        self.assertEqual(len(self.records), FileRecord.objects.count())

        # Without dry flag, submit_delete should be called
        self.command.handle(action='removelocal', lab='lab1', before=str(before_date), y=True)
        client_mock().submit_delete.assert_called()
        delete_clients = [x.args[0] for x in client_mock().submit_delete.call_args_list]
        # This check is a little convoluted...
        # Expect to add delete items for only one endpoint
        delete_clients = [x for x in delete_clients if x.add_item.called]
        self.assertEqual(1, len(delete_clients))
        # The endpoint should match the lab ('lab1')
        repo = DataRepository.objects.get(globus_endpoint_id=delete_clients[0]['endpoint'])
        self.assertEqual('lab1_local', repo.name)
        deleted_files = [x.args[0] for x in delete_clients[0].add_item.call_args_list]
        expected = ['/mnt/foo/subject/2020-01-01/001/imaging.frames.tar.bz2',
                    '/mnt/foo/subject/2020-01-01/001/ephysData.raw.ap.bin']
        self.assertEqual(deleted_files, expected)
        # Check files deleted
        fr = list(
            (FileRecord
                .objects
                .filter(data_repository__name='lab1_local')
                .values_list('relative_path', flat=True))
        )
        self.assertEqual(['subject/2020-01-01/001/foo.bar.baz'], fr)

    def _new_delete_client(self, _, gid, **kwargs):
        """Upon calling DeleteData, return dict-like mock"""
        d = {'DATA': kwargs, 'endpoint': str(gid)}
        self.delete_clients.append(mock.MagicMock(name=f'delete_obj_{gid}'))
        self.delete_clients[-1].__getitem__.side_effect = d.__getitem__
        return self.delete_clients[-1]

    @staticmethod
    def _dataset_uuid_name(dataset):
        return f'{Path(dataset.name).stem}.{dataset.pk}{Path(dataset.name).suffix}'
