"""Tests for actions admin pages.

c.f. subjects tests_admin.py
"""
from datetime import date, timedelta, datetime
from unittest.mock import MagicMock

from django.test import TestCase
from django.contrib.admin.sites import AdminSite

from misc.models import LabMember
from subjects.models import Subject
from actions.models import WaterAdministration, WaterRestriction, Weighing
from actions.admin import WaterAdministrationAdmin, WeighingAdmin
from alyx.test_base import setup_admin_subject_user


class TestWaterAdministrationForm(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup_admin_subject_user(self)  # create a user and a subject
        self.site = AdminSite()
        self.water_admin = WaterAdministrationAdmin(WaterAdministration, self.site)
        self.request = MagicMock()
        self.request.user = self.user
        self.request.session = {}

    def test_subject_list(self):
        """Test that the subject list is ordered by water restricted and alive."""
        # Add a second user and a second subject to test subject list filter
        user2 = LabMember.objects.create_user(username='bar', password='foo123')
        extra_subjects = [
            Subject.objects.create(
                nickname=f'subject{i}', lab=self.lab, responsible_user=self.user)
            for i in range(0, 3)]
        for subject in extra_subjects:
            WaterRestriction.objects.create(subject=subject, start_time=datetime.now())
        # Make one subject's responsible user the second user
        extra_subjects[-1].responsible_user = user2
        extra_subjects[-1].save()
        # Make another deceased
        extra_subjects[-2].death_date = date.today()
        extra_subjects[-2].save()

        form_data = {
            'user': self.user,
            'date_time': datetime.now(),
            'subject': self.subject,
            'water_administered': 1.,
            'adlib': False
        }
        Form = self.water_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        # Check that subjects are filtered by responsible user and alive
        # Expect user2's subject not to be in list, and dead subject should be at the end
        subject_ids = form.fields['subject'].choices.queryset.values_list('pk', flat=True)
        expected = [extra_subjects[0].pk, self.subject.pk, extra_subjects[1].pk]
        self.assertEqual(list(subject_ids), expected)
        # Add last subject id and check that it is first in the list
        self.request.session['last_subject_id'] = self.subject.pk
        Form = self.water_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        subject_ids = form.fields['subject'].choices.queryset.values_list('pk', flat=True)
        expected = [self.subject.pk, extra_subjects[0].pk, extra_subjects[1].pk]
        self.assertEqual(list(subject_ids), expected)

    def test_validation(self):
        """Test validation of the WaterAdministrationForm."""
        form_data = {
            'user': self.user,
            'date_time_0': date.today(),
            'date_time_1': datetime.now().strftime('%H:%M:%S'),
            'subject': self.subject,
            'water_administered': 1.,
            'adlib': False
        }
        Form = self.water_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        self.assertTrue(form.is_valid())

        # Test with dead subject
        self.subject.death_date = date.today()
        self.subject.save()
        self.assertTrue(form.is_valid())
        form_data['date_time_0'] = date.today() + timedelta(days=1)
        form = Form(data=form_data, instance=self.subject)
        self.assertFalse(form.is_valid())
        self.assertIn('date_time', form.errors)
        self.assertEqual(form.errors['date_time'], ['Date must be before subject death date.'])


class TestWeighingForm(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup_admin_subject_user(self)  # create a user and a subject
        self.site = AdminSite()
        self.weight_admin = WeighingAdmin(Weighing, self.site)
        self.request = MagicMock()
        self.request.user = self.user
        self.request.session = {}

    def test_subject_list(self):
        """Test that the subject list is ordered by water restricted and alive."""
        # Add a second user and a second subject to test subject list filter
        user2 = LabMember.objects.create_user(username='bar', password='foo123')
        extra_subjects = [
            Subject.objects.create(
                nickname=f'subject{i}', lab=self.lab, responsible_user=self.user)
            for i in range(0, 3)]
        # Make one subject's responsible user the second user
        extra_subjects[0].responsible_user = user2
        extra_subjects[0].save()
        # Make another deceased
        extra_subjects[1].death_date = date.today()
        extra_subjects[1].save()

        form_data = {
            'user': self.user,
            'date_time_0': date.today(),
            'date_time_1': datetime.now().strftime('%H:%M:%S'),
            'subject': self.subject,
            'weight': 22.
        }
        Form = self.weight_admin.get_form(self.request)
        form = Form(data=form_data, instance=self.subject)
        # Check that subjects are filtered by responsible user and alive
        # Expect user2's subject not to be in list, and dead subject should be at the end
        subject_ids = form.fields['subject'].choices.queryset.values_list('nickname', flat=True)
        expected = [self.subject.nickname, extra_subjects[2].nickname, extra_subjects[1].nickname]
        self.assertEqual(list(subject_ids), expected)
