"""Tests for Subject admin pages."""
from datetime import date, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.test import Client
from django.contrib.admin.sites import AdminSite

from misc.models import LabMember, Lab
from subjects.models import Subject
from actions.models import Cull, CullMethod, CullReason
from misc.management.commands.set_user_permissions import Command
from subjects.admin import CullForm, SubjectAdmin


def setup(obj):
    obj.client = Client()
    obj.user = LabMember.objects.create_user(
        username='foo', password='bar123', email='foo@example.com')
    obj.user.is_staff = obj.user.is_active = True  # for change permissions
    obj.user.save()

    Command().handle()  # set user group permissions
    obj.client.login(username='foo', password='bar123')
    obj.lab = Lab.objects.get(name='cortexlab')
    obj.subject = Subject.objects.create(
        nickname='aQt', birth_date=date(2025, 1, 1), lab=obj.lab, actual_severity=2)


class TestSubjectCullForm(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup(self)
        self.cull_methods = [CullMethod.objects.create(name=f'method{i}') for i in range(0, 2)]
        self.cull_reasons = [CullReason.objects.create(name=f'reason{i}') for i in range(0, 2)]

    def test_cull_date_before_birth_date(self):
        """Test that cull date must be after birth date."""
        form_data = {
            'user': self.user,
            'date': date(2019, 12, 31),
            'cull_method': self.cull_methods[1],
            'cull_reason': self.cull_reasons[0],
            'description': 'Description'
        }
        form = CullForm(data=form_data, instance=Cull(subject=self.subject))
        self.assertFalse(form.is_valid())
        self.assertIn('date', form.errors)
        self.assertEqual(form.errors['date'], ['Cull date must be after birth date.'])

    def test_valid_form(self):
        """Test that a valid form is accepted."""
        form_data = {
            'user': self.user,
            'date': self.subject.birth_date + timedelta(days=1),
            'cull_method': self.cull_methods[1],
            'cull_reason': self.cull_reasons[0],
            'description': 'Description'
        }
        form = CullForm(data=form_data, instance=Cull(subject=self.subject))
        self.assertTrue(form.is_valid())


class TestSubjectAdminForm(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup(self)
        self.site = AdminSite()
        self.subject_admin = SubjectAdmin(Subject, self.site)
        self.request = MagicMock()
        self.request.user = self.user

    def test_clean_responsible_user(self):
        """Test that responsible user cannot be changed by unauthorized users."""
        # Create another user to act as the old responsible user
        old_responsible_user = LabMember.objects.create_user(
            username='old_user', password='old_pass', email='old_user@example.com')
        self.subject.responsible_user = old_responsible_user
        self.subject.save()

        # Attempt to change the responsible user
        form_data = {'responsible_user': self.user}
        Form = self.subject_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        self.assertFalse(form.is_valid())
        self.assertIn('responsible_user', form.errors)
        expected = ['You are not allowed to change the responsible user.']
        self.assertEqual(expected, form.errors['responsible_user'])

        # Allow the change by making the logged-in user a superuser
        self.user.is_superuser = True
        self.user.save()
        form = Form(data=form_data, instance=self.subject)
        self.assertTrue(form.is_valid() or 'responsible_user' not in form.errors)

    def test_clean_reduced_date(self):
        """Test that reduced date must be after birth date."""
        form_data = {
            'responsible_user': self.user,
            'reduced_date': date(2024, 12, 31),
            'birth_date': date(2025, 1, 1),
        }
        Form = self.subject_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        self.assertFalse(form.is_valid())
        self.assertIn('reduced_date', form.errors)
        self.assertEqual(form.errors['reduced_date'], ['Reduced date must be after birth date.'])

        form_data['reduced_date'] = date(2025, 1, 2)
        form = Form(data=form_data, instance=self.subject)
        self.assertTrue(form.is_valid() or 'reduced_date' not in form.errors)

        # Now add a cull and test that reduced date must be after cull date
        Cull.objects.create(
            user=self.user, date=date(2025, 1, 3), subject=self.subject)
        form = Form(data=form_data, instance=self.subject)
        self.assertFalse(form.is_valid())
        self.assertIn('reduced_date', form.errors)
        self.assertEqual(form.errors['reduced_date'], ['Reduced date must be after cull date.'])

    def test_clean_actual_severity(self):
        """Test that actual severity must be set when adding a cull."""
        form_data = {
            'responsible_user': self.user,
            'birth_date': date(2025, 1, 1),
            'actual_severity': None,  # missing actual severity
            'cull-0-date': date(2025, 2, 1),  # adding a cull
        }
        Form = self.subject_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        self.assertFalse(form.is_valid())
        self.assertIn('actual_severity', form.errors)
        expected = ['Actual severity field must not be null when adding a cull.']
        self.assertEqual(expected, form.errors['actual_severity'])

        form_data['actual_severity'] = 2  # Valid actual severity
        form = Form(data=form_data, instance=self.subject)
        self.assertTrue(form.is_valid() or 'actual_severity' not in form.errors)
