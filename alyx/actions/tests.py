import datetime
import numpy as np
from django.test import TestCase

from actions.models import WaterAdministration, WaterRestriction, WaterType, Weighing
from subjects.models import Subject
from misc.models import Lab


class WaterControlTests(TestCase):
    def setUp(self):
        # create some water types
        wtypes = ['Water', 'Hydrogel', 'CA 5% Hydrogel', 'CA 5%', 'Sucrose 10%']
        for wt in wtypes:
            WaterType.objects.create(name=wt)
        # create a subject
        sub = Subject.objects.create(nickname='bigboy', birth_date='2018-09-01')
        self.sub = Subject.objects.get(pk=sub.pk)
        # 50 days of loosing weight and getting 0.98 mL water
        self.start_date = datetime.datetime(year=2018, month=10, day=1)
        self.rwind = 5  # water restriction will start on the fifth day
        self.wei = np.linspace(25, 20, 50)
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
        # create labs with different weight measurement techniques
        Lab.objects.create(name='zscore', reference_weight_pct=0, zscore_weight_pct=0.85)
        Lab.objects.create(name='rweigh', reference_weight_pct=0.85, zscore_weight_pct=0)
        Lab.objects.create(name='mixed', reference_weight_pct=0.425, zscore_weight_pct=0.425)
        # Create an initial Water Restriction
        start_wr = self.start_date + datetime.timedelta(days=self.rwind)
        water_type = WaterType.objects.get(name='CA 5% Hydrogel')
        self.wr = WaterRestriction.objects.create(subject=self.sub, start_time=start_wr,
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

    def test_water_control_thresholds(self):
        # test computation on reference weight lab alone
        self.sub.lab = Lab.objects.get(reference_weight_pct=0.85)
        self.sub.save()
        wc = self.sub.water_control
        wc.expected_weight()
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        self.assertAlmostEqual(self.wei[self.rwind], wc.expected_weight())
        # test computation on zscore weight lab alone
        self.sub.lab = Lab.objects.get(reference_weight_pct=0)
        self.sub.save()
        wc = self.sub.water_control
        wc.expected_weight()
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        zscore = wc.zscore_weight()
        # test computation on mixed lab
        self.sub.lab = Lab.objects.get(reference_weight_pct=0.425)
        self.sub.save()
        wc = self.sub.water_control
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        self.assertAlmostEqual(wc.expected_weight(), (wc.reference_weight() + zscore) / 2)
