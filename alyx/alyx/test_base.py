from datetime import date

from django.test import TestCase
from django.test import Client
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


def setup_admin_subject_user(obj):
    """Set up a user with permissions to access the admin site and a subject."""
    from misc.models import LabMember, Lab
    from subjects.models import Subject
    from misc.management.commands.set_user_permissions import Command

    obj.client = Client()
    obj.user = LabMember.objects.create_user(
        username='foo', password='bar123', email='foo@example.com')
    obj.user.is_staff = obj.user.is_active = True  # for change permissions
    obj.user.save()

    Command().handle()  # set user group permissions
    obj.client.login(username='foo', password='bar123')
    try:
        obj.lab = Lab.objects.get(name='cortexlab')
    except Lab.DoesNotExist:
        obj.Lab = Lab.objects.create(name='cortexlab')
    obj.subject = Subject.objects.create(
        nickname='aQt', birth_date=date(2025, 1, 1), lab=obj.lab, actual_severity=2)
