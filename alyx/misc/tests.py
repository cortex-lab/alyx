from datetime import datetime, timedelta
import unittest
from django.test import TestCase

from subjects.models import Subject
from misc.models import Housing, HousingSubject, CageType

SKIP_ONE_CACHE = False
try:
    import pyarrow as pa
    from misc.management.commands import one_cache
except ImportError as ex:
    print(f'Failed to import one_cache: {ex}')
    SKIP_ONE_CACHE = True


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

    def test_s3_filesystem(self):
        """Test the _s3_filesystem function"""
        region = 'eu-east-1'
        s3 = one_cache._s3_filesystem(region=region)
        self.assertIsInstance(s3, pa.fs.S3FileSystem)
        self.assertEqual(s3.region, region)
