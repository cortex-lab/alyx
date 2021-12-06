from uuid import uuid4

from django.test import TestCase

from . import transfers


class TransferUtilTests(TestCase):
    def test_add_uuid_to_filename(self):
        uuid = uuid4()
        expected = f'spikes.times.{uuid}.npy'
        testable = transfers._add_uuid_to_filename('spikes.times.npy', uuid)
        self.assertEqual(expected, testable)
        # Check leaves UUID if already added
        self.assertEqual(expected, transfers._add_uuid_to_filename(testable, uuid))
