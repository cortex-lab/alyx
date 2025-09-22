"""Tests for Subject admin pages."""
from datetime import date, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.contrib.admin.sites import AdminSite

from alyx.test_base import setup_admin_subject_user
from misc.models import LabMember
from subjects.models import Subject, BreedingPair
from actions.models import Cull, CullMethod, CullReason
from subjects.admin import CullForm, SubjectAdmin, BreedingPairAdminForm


class TestBreedingPairAdmin(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        self.site = AdminSite()
        setup_admin_subject_user(self)

    def test_set_end_date_with_culled_subject(self):
        lab_member_stock_manager = LabMember.objects.create_user(
            username='stock_manager', password='bar123', email='foo@example.com', is_staff=True, is_active=True, is_stock_manager=True)
        kwargs_subjects = dict(birth_date=date(2025, 1, 1), lab=self.lab, responsible_user=lab_member_stock_manager)
        father = Subject.objects.create(nickname='father', sex='M', **kwargs_subjects)
        mother1 = Subject.objects.create(nickname='mother1', sex='F', **kwargs_subjects)
        breeding_pair = BreedingPair.objects.create(father=father, mother1=mother1, mother2=None)
        # the form is valid as both parents are alive
        form_data = {
        'json': breeding_pair.json,
            'description': breeding_pair.description,
            'name': breeding_pair.name,
         'line': breeding_pair.line,
         'start_date': breeding_pair.start_date,
         'end_date': breeding_pair.end_date,
         'father': breeding_pair.father,
         'mother1': breeding_pair.mother1,
         'mother2': breeding_pair.mother2,
         }
        form_instance = BreedingPairAdminForm(data=form_data, instance=breeding_pair)
        self.assertTrue(form_instance.is_valid())
        # the form is still valid once the father is culled: it can´t  be set on a new breeding pair,
        # but it can remain on this one and the form is valid
        # but it can remain on this one and the form is valid
        Cull(subject=father, user=lab_member_stock_manager, date=date(2025, 6, 1))
        father.save()
        form_instance = BreedingPairAdminForm(data=form_data, instance=breeding_pair)
        self.assertTrue(form_instance.is_valid())


class TestSubjectCullForm(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup_admin_subject_user(self)
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
        setup_admin_subject_user(self)
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
