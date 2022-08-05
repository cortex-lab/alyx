from django.test import TestCase
from django.db.utils import IntegrityError
from data.models import Dataset, DatasetType
from data.transfers import get_dataset_type


class TestModel(TestCase):
    def test_model_methods(self):
        (dset, _) = Dataset.objects.get_or_create(name='toto.npy')
        assert dset.is_online is False
        assert dset.is_public is False
        assert dset.is_protected is False


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
        for filename, dataname in filename_typename:
            with self.subTest(filename=filename):
                self.assertEqual(get_dataset_type(filename).name, dataname)
