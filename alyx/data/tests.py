from django.test import TestCase
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import ProtectedError

from data.models import Dataset, DatasetType, Tag
from subjects.models import Subject
from data.transfers import get_dataset_type


class TestModel(TestCase):
    def test_model_methods(self):
        (dset, _) = Dataset.objects.get_or_create(name='toto.npy')

        self.assertIs(dset.is_online, False)
        self.assertIs(dset.is_public, False)
        self.assertIs(dset.is_protected, False)

    def test_generic_foreign_key(self):
        # Attempt to associate a dataset with a subject
        (subj, _) = Subject.objects.get_or_create(nickname='foobar')
        dset = Dataset(name='toto.npy', content_object=subj)

        self.assertIs(dset.content_object, subj)

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
