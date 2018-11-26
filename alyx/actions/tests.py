import datetime
import numpy as np
from django.test import TestCase

from actions.models import WaterAdministration, WaterRestriction, WaterType, Weighing
from subjects.models import Subject


class WaterControlTests(TestCase):
    def setUp(self):
        # create some water types
        wtypes = ['Water', 'Hydrogel', 'CA 5% Hydrogel', 'CA 5%', 'Sucrose 10%']
        for wt in wtypes:
            WaterType.objects.create(name=wt)
        # create a subject
        self.sub = Subject.objects.create(nickname='bigboy', birth_date='2018-09-01')
        # 50 days of loosing weight and getting 0.98 mL water
        self.start_date = datetime.datetime(year=2018, month=10, day=1)
        for n, w in enumerate(np.linspace(25, 20, 50)):
            date_w = datetime.timedelta(days=n) + self.start_date
            Weighing.objects.create(weight=w, subject=self.sub, date_time=date_w)
            WaterAdministration.objects.create(
                water_administered=0.98,
                subject=self.sub,
                date_time=date_w)
        # first test assert that water administrations previously created have the correct default
        wa = WaterAdministration.objects.filter(subject=self.sub)
        self.assertTrue(wa.values_list('water_type__name').distinct()[0][0] == 'Water')

    def test_00_create_first_water_restriction(self):
        # Create an initial Water Restriction
        start_wr = self.start_date + datetime.timedelta(days=5)
        water_type = WaterType.objects.get(name='CA 5% Hydrogel')
        WaterRestriction.objects.create(subject=self.sub, start_time=start_wr,
                                        water_type=water_type)
        # from now on new water administrations should have water_type as default
        wa = WaterAdministration.objects.create(
            water_administered=1.02,
            subject=self.sub,
            date_time=datetime.datetime.now())
        self.assertEqual(water_type, wa.water_type)

    def test_water_administration_expected(self):
        wc = self.sub.water_control
        wa = WaterAdministration.objects.filter(subject=self.sub)
        # the method from the wa model should return the expectation at the corresponding date
        self.assertTrue(wa[0].expected() == wc.expected_water(date=wa[0].date_time.date()))
        self.assertTrue(wa[40].expected() == wc.expected_water(date=wa[40].date_time.date()))
