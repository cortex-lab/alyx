from django.test import TestCase
from alyx.base import _custom_filter_parser


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
            ('f0,["toto"],f1,["tata"]', {"f0": ["toto"], "f1": ['tata']}),
            ('f0,val0,f1,("tata")', {"f0": "val0", "f1": 'tata'}),
            ('f0,val0,f1,("tata",)', {"f0": "val0", "f1": ('tata',)})
        ]

        for fix in fixtures:
            self.assertEqual(_custom_filter_parser(fix[0]), fix[1])

        def value_error_on_duplicate_field():
            _custom_filter_parser('toto,abc,toto,1')
        self.assertRaises(ValueError, value_error_on_duplicate_field)
