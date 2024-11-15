import zipfile
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import unittest
from django.test import TestCase
from one.alf.spec import QC
from one.alf.cache import DATASETS_COLUMNS, SESSIONS_COLUMNS
import pandas as pd

from subjects.models import Subject
from misc.models import Housing, HousingSubject, CageType, LabMember, Lab
from actions.models import Session
from data.models import Dataset, DatasetType, DataRepository, FileRecord, DataFormat

SKIP_ONE_CACHE = False
try:
    import pyarrow as pa
    from misc.management.commands import one_cache
except ImportError as ex:
    print(f'Failed to import one_cache: {ex}')
    SKIP_ONE_CACHE = True


class LabMemberTests(TestCase):
    def setUp(self):
        lab = Lab.objects.create(name='multi_user_lab')
        self.lab_member_0 = LabMember.objects.create(username='test_user', is_stock_manager=True)
        self.lab_member_a = LabMember.objects.create(username='test_user_a')
        self.lab_member_b = LabMember.objects.create(username='test_user_b')
        self.lab_member_b.allowed_users.set([self.lab_member_a])
        self.subject_a = Subject.objects.create(nickname='subject_a', lab=lab,
                                                responsible_user=self.lab_member_a)
        self.subject_b = Subject.objects.create(nickname='subject_b', lab=lab,
                                                responsible_user=self.lab_member_b)
        self.subject_c = Subject.objects.create(nickname='subject_c', lab=lab)

    def test_allowed_users(self):
        # stock manager sees all of the subjects
        sub_stock_manager = set(
            self.lab_member_0.get_allowed_subjects().values_list('nickname', flat=True))
        self.assertEqual(sub_stock_manager, set(['subject_a', 'subject_b', 'subject_c']))
        # lab_member_a has delegate access to lab_member_b, so sees subject_b
        sub_lab_member_a = set(
            self.lab_member_a.get_allowed_subjects().values_list('nickname', flat=True))
        self.assertEqual(sub_lab_member_a, set(['subject_a', 'subject_b']))
        # lab_member_b sees only her subjects
        sub_lab_member_b = set(
            self.lab_member_b.get_allowed_subjects().values_list('nickname', flat=True))
        self.assertEqual(sub_lab_member_b, set(['subject_b']))


class HousingTests(TestCase):
    fixtures = ['misc.cagetype.json', 'misc.enrichment.json', 'misc.food.json', 'misc.lab.json']

    def setUp(self):
        """
        hou1 contains sub1
        hou2 contains sub2 and sub3
        """
        Subject.objects.create(nickname='sub1')
        Subject.objects.create(nickname='sub2')
        Subject.objects.create(nickname='sub3')
        Housing.objects.all().delete()
        HousingSubject.objects.all().delete()
        self.hou1 = Housing.objects.create(cage_name='housing_1')
        subs1 = Subject.objects.filter(cull__isnull=True)[0:1]
        for sub in subs1:
            HousingSubject.objects.create(subject=sub, housing=self.hou1,
                                          start_datetime=datetime.now() - timedelta(seconds=3600))
        self.hou2 = Housing.objects.create(cage_name='housing_2')
        subs2 = Subject.objects.filter(cull__isnull=True)[1:]
        for sub in subs2:
            HousingSubject.objects.create(subject=sub, housing=self.hou2,
                                          start_datetime=datetime.now() - timedelta(seconds=3600))

    def test_housing_subjects_current(self):
        # as per the setup above, first housing has one current subject
        sub1 = Subject.objects.filter(pk__in=self.hou1.subjects_current())
        self.assertEqual(list(sub1.values_list('nickname', flat=True)), ['sub1'])
        # as per the setup above, second housing has 2 current subjects
        sub2 = Subject.objects.filter(pk__in=self.hou2.subjects_current())
        self.assertEqual(list(sub2.values_list('nickname', flat=True)), ['sub2', 'sub3'])
        # if we remove sub2 subject manually, then current subject is sub3
        hs = HousingSubject.objects.get(housing=self.hou2, subject__nickname='sub2')
        hs.end_datetime = datetime.now() - timedelta(seconds=1800)
        hs.save()
        sub2 = Subject.objects.filter(pk__in=self.hou2.subjects_current())
        self.assertEqual(list(sub2.values_list('nickname', flat=True)), ['sub3'])
        # if we query at the start of the test, sub2 only
        sub2 = Subject.objects.filter(pk__in=self.hou2.subjects_current(
            datetime=hs.start_datetime + timedelta(seconds=600)))
        self.assertEqual(list(sub2.values_list('nickname', flat=True)), ['sub2'])

    def test_change_housing_field(self):
        self.hou1.cage_type = CageType.objects.first()
        self.hou1.save()
        # the housing is duplicated
        self.assertTrue(Housing.objects.filter(cage_name='housing_1').count() == 2)
        # the original housing doesn't have any mouse
        hs = self.hou1.housing_subjects.all()
        self.assertTrue(hs.count() == 1)
        self.assertTrue(hs[0].end_datetime is None)
        # the new housing is identifiable by the fact it has no end date
        hou1_old = Housing.objects.filter(cage_name='housing_1').exclude(pk=self.hou1.pk)
        self.assertTrue(hou1_old.count() == 1)
        self.assertTrue(hou1_old[0].cage_type is None)
        self.assertFalse(hou1_old[0].housing_subjects.all()[0].end_datetime is None)
        hs = hou1_old[0].housing_subjects.all()
        self.assertTrue(hs.count() == 1)
        self.assertFalse(hs[0].end_datetime is None)
        self.assertEqual(hs[0].subject.nickname, 'sub1')

    def test_change_housing_field_no_current_subjects(self):
        # first close all the subjects for the first housing
        hs = self.hou1.housing_subjects.first()
        hs.end_datetime = datetime.now()
        hs.save()
        # then update one field of housing: should result in duplication
        self.hou1.cage_type = CageType.objects.first()
        self.hou1.save()
        # the housing is duplicated
        self.assertTrue(Housing.objects.filter(cage_name='housing_1').count() == 2)
        # all housings don't have any mouse
        for hou in Housing.objects.filter(cage_name='housing_1'):
            self.assertTrue(hou.subjects_current().count() == 0)

    def test_set_housingsubjects_end_datetime(self):
        # in this case the housingsubject is just closed
        hs = self.hou1.housing_subjects.first()
        hs.end_datetime = datetime.now()
        hs.save()
        self.assertTrue(self.hou1.subjects_current().count() == 0)
        self.assertTrue(self.hou1.housing_subjects.count() == 1)

    def test_remove_subject(self):
        self.assertTrue(self.hou2.subjects_current().count(), 2)
        hs = HousingSubject.objects.get(housing=self.hou2, subject__nickname='sub2')
        hs.end_datetime = datetime.now() - timedelta(seconds=2)
        self.assertTrue(self.hou2.subjects_current().count(), 1)

    def test_move_subject(self):
        self.assertEqual(self.hou2.subjects_current().count(), 2)
        self.assertEqual(self.hou1.subjects_current().count(), 1)
        sub2 = Subject.objects.get(nickname='sub2')
        HousingSubject.objects.create(housing=self.hou1,
                                      subject=sub2,
                                      start_datetime=datetime.now())
        self.assertEqual(self.hou2.subjects_current().count(), 1)
        self.assertEqual(self.hou1.subjects_current().count(), 2)


@unittest.skipIf(SKIP_ONE_CACHE, 'Missing dependencies')
class ONECache(TestCase):
    """Tests for misc.management.commands.one_cache"""
    fixtures = [
        'data.datarepositorytype.json', 'data.datasettype.json',
        'data.dataformat.json', 'misc.lab.json'
    ]

    def setUp(self):
        self.command = one_cache.Command()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        # Create some sessions and datasets
        lab = Lab.objects.first()
        subject = Subject.objects.create(nickname='586', lab=lab)
        repo = DataRepository.objects.create(
            name='flatiron', globus_path='foo', lab=lab, globus_is_personal=True)
        for i in range(5):
            session = Session.objects.create(
                subject=subject, number=i + 1, type='Experiment', task_protocol='foo', qc=QC.PASS)
            for d in ('foo.bar.npy', 'bar.baz.bin'):
                dtype, _ = DatasetType.objects.get_or_create(name=Path(d).stem)
                format = DataFormat.objects.get(name=Path(d).suffix[1:])
                dataset = Dataset.objects.create(
                    session=session, dataset_type=dtype, collection='alf', qc=QC.PASS,
                    name=d, data_format=format, file_size=(1024 * i) or None)
                p = (f'{session.subject.nickname}/{session.start_time.date()}'
                     f'/{session.number:03d}/alf/{d}')
                FileRecord.objects.create(
                    relative_path=p, dataset=dataset, data_repository=repo, exists=True)

    def test_generate_tables(self):
        """Test ONE cache table generation."""
        # Check table name validation
        self.assertRaises(ValueError, self.command.handle, verbosity=1, tables=('foo',))
        # Check table generation
        self.command.handle(
            destination=str(self.tmp), compress=False, verbosity=1,
            tables=('sessions', 'datasets')
        )
        self.assertCountEqual(
            ['date_created', 'origin', 'min_api_version'], self.command.metadata)
        tables = sorted(self.tmp.glob('*.pqt'))
        self.assertEqual(len(tables), 2)
        datasets, sessions = pd.read_parquet(tables[0]), pd.read_parquet(tables[1])
        self.assertCountEqual(
            datasets.reset_index().columns, DATASETS_COLUMNS + ('default_revision',))
        self.assertTrue(all(datasets['rel_path'].str.startswith('alf/')))
        self.assertCountEqual(sessions.reset_index().columns, SESSIONS_COLUMNS)
        # Test QC and compression
        self.command.handle(
            destination=str(self.tmp), compress=True, verbosity=1, tables=('sessions',), qc=True)
        zip_file = self.tmp / 'cache.zip'
        self.assertTrue(zip_file.exists())
        cache_info = self.tmp / 'cache_info.json'
        self.assertTrue(cache_info.exists())
        zip = zipfile.ZipFile(zip_file)
        self.assertCountEqual(['sessions.pqt', 'cache_info.json', 'QC.json'], zip.namelist())

    def test_s3_filesystem(self):
        """Test the _s3_filesystem function"""
        region = 'eu-east-1'
        s3 = one_cache._s3_filesystem(region=region)
        self.assertIsInstance(s3, pa.fs.S3FileSystem)
        self.assertEqual(s3.region, region)
