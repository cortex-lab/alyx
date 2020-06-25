from django.test import TestCase
from alyx.base import _custom_filter_parser

# TODO change output as a list
# TODO for loop on queries so the same keyword can be utilized twice
# TODO fix double keyword list on regex
# those 3 items should not change the client side syntax in anyway


class BaseCustomFilterTest(TestCase):

    def test_parser(self):
        fixtures = [
            ('gnagna,["NYU-21", "SH014"]', {"gnagna": ["NYU-21", "SH014"]}),  # list
            ("gnagna,['NYU-21', 'SH014']", {"gnagna": ["NYU-21", "SH014"]}),  # list
            ('fieldname,None', {"fieldname": None}),  # None
            ('fieldname,true', {"fieldname": True}),  # True insensitive
            ('fieldname,True', {"fieldname": True}),  # True
            ('fieldname,False', {"fieldname": False}),  # False
            ('fieldname,NYU', {"fieldname": "NYU"}),  # string
            ('fieldname,14.2', {"fieldname": 14.2}),  # float
            ('fieldname,142', {"fieldname": 142}),  # integer
            # ('f0,["toto"],f1,["tata"]', {"f0": ["toto"], "f1": ['tata']})  # TODO
        ]

        for fix in fixtures:
            self.assertEqual(_custom_filter_parser(fix[0]), fix[1])
