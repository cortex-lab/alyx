from uuid import uuid4

from django.test import TestCase
from data.models import Dataset

from . import transfers


class TransferUtilTests(TestCase):
    def test_add_uuid_to_filename(self):
        uuid = uuid4()
        expected = f'spikes.times.{uuid}.npy'
        testable = transfers._add_uuid_to_filename('spikes.times.npy', uuid)
        self.assertEqual(expected, testable)
        # Check leaves UUID if already added
        self.assertEqual(expected, transfers._add_uuid_to_filename(testable, uuid))


class TestModel(TestCase):
    def test_model_methods(self):
        (dset, _) = Dataset.objects.get_or_create(name='toto.npy')
        assert dset.is_online is False
        assert dset.is_public is False
        assert dset.is_protected is False
