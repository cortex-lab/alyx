from datetime import datetime, timedelta
from django.test import TestCase

from subjects.models import Subject
from misc.models import Housing, CageType


class HousingTests(TestCase):
    fixtures = ['misc.cagetype.json', 'misc.enrichment.json', 'misc.food.json']

    def setUp(self):
        Subject.objects.create(nickname='sub1')
        Subject.objects.create(nickname='sub2')
        Subject.objects.create(nickname='sub3')
        Subject.objects.create(nickname='sub4')
        Subject.objects.create(nickname='sub5')

    def test_field_update(self):
        # first create the initial object
        hou = Housing.objects.create(start_datetime=datetime.now() - timedelta(seconds=3600),
                                     light_cycle=1)
        subs = Subject.objects.all()[:2]
        hou.subjects.set(subs)
        self.assertTrue(Housing.objects.count() == 1)

        # then make sure by assigning an end-date, the object doesn't duplicate
        hou.end_datetime = datetime.now()
        hou.save()
        self.assertTrue(Housing.objects.get(pk=hou.pk).end_datetime == hou.end_datetime)
        self.assertTrue(Housing.objects.count() == 1)
        hou.end_datetime = None
        hou.save()
        initial_pk = hou.pk
        self.assertTrue(Housing.objects.get(pk=hou.pk).end_datetime is None)
        self.assertTrue(Housing.objects.count() == 1)

        # make sure that a change of cagetype for example triggers a duplication & fills end date
        hou.cage_type = CageType.objects.get(name='GM500')
        hou.save()
        old_housing = Housing.objects.get(pk=initial_pk)
        new_housing = Housing.objects.get(pk=hou.pk)
        self.assertTrue(old_housing.cage_type is None)
        self.assertTrue(old_housing.end_datetime is not None)
        self.assertTrue(new_housing.cage_type.name == 'GM500')
        self.assertTrue(new_housing.end_datetime is None)
        # the end datetime of the first object should match the start date time of the new object
        self.assertTrue(new_housing.start_datetime == old_housing.end_datetime)

    def test_switch_subject_housing(self):
        # case where a mouse is moved from a cage to another: this should duplicate both cages
        # first create the two initial objects
        hou1 = Housing.objects.create(start_datetime=datetime.now() - timedelta(seconds=3600),
                                      light_cycle=1)
        subs1 = Subject.objects.all()[0]
        hou1.subjects.set([subs1])
        hou2 = Housing.objects.create(start_datetime=datetime.now() - timedelta(seconds=3600),
                                      light_cycle=1)
        subs2 = Subject.objects.all()[1:4]
        hou2.subjects.set(subs2)
        self.assertTrue(Housing.objects.count() == 2)

        # emulate the admin interface by creating an empty shell
        obj = Housing.objects.create(start_datetime=datetime.now(), light_cycle=1)
        subs = Subject.objects.all()[0:2].values_list('pk', flat=True)

        housings = Housing.objects.filter(end_datetime__isnull=True).exclude(pk=obj.pk)
        housings = housings.filter(subjects__pk__in=subs).distinct()
        obj.update_and_create(housings, moved_subjects_pk=subs)
        self.assertTrue(Housing.objects.count() == 4)
        self.assertTrue(Housing.objects.filter(end_datetime__isnull=True).count() == 2)
