from random import choice, randint, random

from django.db import transaction
from django.core.exceptions import ValidationError

from alyx.base import BaseTests
from actions.models import Session
from experiments.models import ProbeInsertion, ImagingType, FOV, FOVLocation, ImagingStack
from data.models import Dataset


class EphysModels(BaseTests):

    def test_create_probe_insertion(self):

        ses = Session.objects.first()
        Dataset.objects.create(session=ses, name='toto.csv', collection='alf/probe00')
        data = {'session': ses,
                'serial': 18194815721,
                'name': 'probe00',
                'json': {'qc': 'NOT_SET', 'extended_qc': {}}}
        pi = ProbeInsertion.objects.create(**data)
        assert pi.datasets.all().count() == 1


class ImagingModels(BaseTests):
    def test_create_fov(self):
        ses = Session.objects.first()
        typ, _ = ImagingType.objects.get_or_create(name='two-photon')
        Dataset.objects.create(session=ses, name='foo.npy', collection='alf/fov_00')
        data = {'session': ses, 'imaging_type': typ, 'name': 'fov_00'}
        fov = FOV.objects.create(**data)
        self.assertEqual(1, fov.datasets.count())

        # Create FOV location
        data = {k: [random() + randint(0, 5) * choice([1, -1]) for _ in range(4)] for k in 'xyz'}
        data.update(
            n_xyz=(512, 512, 1), field_of_view=fov, provenance='E', default_provenance=True)
        fov_location = FOVLocation.objects.create(**data)
        data['provenance'] = 'H'
        # Check that there is only one default provenance
        fov_location2 = FOVLocation.objects.create(**data)
        self.assertTrue(fov_location2.default_provenance)
        self.assertFalse(FOVLocation.objects.get(id=fov_location.id).default_provenance)

    def test_create_stack(self):
        """Test fields of view associated with a stack"""
        ses = Session.objects.first()
        ses2 = Session.objects.last()
        assert ses != ses2
        typ, _ = ImagingType.objects.get_or_create(name='two-photon')
        stack = ImagingStack.objects.create()
        data = {'session': ses, 'imaging_type': typ, 'name': 'fov_00', 'stack': stack}
        # Creating a FOV associated to the same stack but with a different session should raise a
        # validation error
        FOV.objects.create(**data)
        data.update(name='fov_01', session=ses2)
        with transaction.atomic():
            self.assertRaises(ValidationError, FOV.objects.create, **data)
