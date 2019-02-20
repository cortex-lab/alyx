from django.test import TestCase

from misc.models import CageType, Enrichment, Food, Housing


class HousingTests(TestCase):
    fixtures = ['misc.cagetype.json', 'misc.enrichment.json', 'misc.food.json']

    def setUp(self):
        a =1
        pass

    def test_toto(self):
        pass

    def tearDown(self):
        pass
