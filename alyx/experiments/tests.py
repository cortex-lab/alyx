from alyx.base import BaseTests

from actions.models import Session
from experiments.models import ProbeInsertion
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
