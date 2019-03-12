from datetime import datetime, timedelta
from django.test import TestCase

from subjects.models import Subject
from misc.models import Housing, HousingSubject, CageType


class HousingTests(TestCase):
    fixtures = ['misc.cagetype.json', 'misc.enrichment.json', 'misc.food.json']

    def setUp(self):
        Subject.objects.create(nickname='sub1')
        Subject.objects.create(nickname='sub2')
        Subject.objects.create(nickname='sub3')
        Housing.objects.all().delete()
        HousingSubject.objects.all().delete()
        self.hou1 = Housing.objects.create(cage_name='housing_1')
        subs1 = Subject.objects.filter(death_date__isnull=True)[0:1]
        for sub in subs1:
            HousingSubject.objects.create(subject=sub, housing=self.hou1,
                                          start_datetime=datetime.now() - timedelta(seconds=3600))
        self.hou2 = Housing.objects.create(cage_name='housing_2')
        subs2 = Subject.objects.filter(death_date__isnull=True)[1:4]
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

    def test_change_housing_subject(self):
        self.hou2.subjects_current()
        self.hou1.subjects_current()
        hs = HousingSubject.objects.get(subject__nickname='sub2')
        hs.subject = Subject.objects.get(nickname='sub1')
        hs.save()
        # in this case the subject 1 and 3 are in cage 2 and subject 2 is nowhere...
        self.assertEqual(self.hou1.subjects_current().count(), 0)
        self.assertEqual(list(self.hou2.subjects_current().values_list('nickname', flat=True)),
                         ['sub1', 'sub3'])
        # but subject 2 was in cage 2 before
        self.assertFalse(HousingSubject.objects.get(subject__nickname='sub2').end_datetime is None)
