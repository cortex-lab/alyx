from django.test import TestCase
from data.models import Dataset


class TestModel(TestCase):
    def test_model_methods(self):
        (dset, _) = Dataset.objects.get_or_create(name='toto.npy')
        assert dset.is_online is False
        assert dset.is_public is False
        assert dset.is_protected is False
