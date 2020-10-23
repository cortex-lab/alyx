from datetime import datetime
import os.path as op
import uuid

from ibllib.io import globus as gl

from alyx.base import BaseTests
from actions.models import Session
from data.models import Dataset, DatasetType, DataFormat, DataRepository, FileRecord
from misc.models import Lab
from subjects.models import Subject
from data.data import get_session_root_path, exist_on_flatiron


class DataTests(BaseTests):
    def setUp(self):
        self.flatiron = DataRepository.objects.create(
            name='flatiron_test',
            data_url='http://ibl.flatironinstitute.org/public/testlab/',
            globus_is_personal=False,
            globus_endpoint_id=gl.ENDPOINTS['flatiron'][0],
            globus_path='/public/testlab/',
            hostname='ibl.flatironinstitute.org',
        )
        self.lab = Lab.objects.create(name='testlab')
        self.lab.repositories.add(self.flatiron)
        self.subject = Subject.objects.create(nickname='testsub', lab=self.lab)
        self.session = Session.objects.create(
            number=1,
            subject=self.subject,
            start_time=datetime.strptime('2020-01-01', '%Y-%m-%d'),
        )
        self.dst = DatasetType.objects.create(name='dst', filename_pattern='name.dst.*')
        self.df = DataFormat.objects.create(name='txt', file_extension='.txt')
        self.dset = Dataset.objects.create(
            file_size=20,
            md5='4221d002ceb5d3c9e9137e495ceaa647',
            dataset_type=self.dst,
            data_format=self.df,
        )

    def tearDown(self):
        self.dset.delete()
        self.df.delete()
        self.dst.delete()
        self.session.delete()
        self.subject.delete()
        self.lab.delete()
        self.flatiron.delete()

    def test_1(self):
        self.assertEqual(exist_on_flatiron(self.session.pk, ['name.dst.txt']), [True])
