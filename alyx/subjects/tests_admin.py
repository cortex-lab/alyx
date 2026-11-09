"""Tests for Subject admin pages."""
from datetime import date, timedelta
from unittest import mock
from unittest.mock import MagicMock

from django.test import TestCase
from django.contrib.admin.models import LogEntry, DELETION, CHANGE
from django.contrib.admin.sites import AdminSite
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone
from reversion.models import Revision

from alyx.test_base import setup_admin_subject_user
from misc.models import LabMember, Note
from subjects.models import Subject, BreedingPair, Line, Litter
from actions.models import Cull, CullMethod, CullReason, Weighing
from subjects import admin as subjects_admin
from subjects.admin import CullForm, SubjectAdmin, BreedingPairAdminForm, BreedingPairInline


class TestLitterRollback(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        setup_admin_subject_user(self)  # self.user is a lab member without delete rights
        self.admin = LabMember.objects.create_user(
            username='admin', password='bar123', is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.line = Line.objects.create(name='Line one', nickname='L1')
        self.bp = BreedingPair.objects.create(line=self.line)
        self.old_litter, self.old_pups = self._litter(2)
        self.litter, self.pups = self._litter(2)  # L1_L_002 with pups L1_0003 and L1_0004
        self.url = reverse('admin:subjects_litter_changelist')

    def _litter(self, n_pups):
        litter = Litter.objects.create(line=self.line, breeding_pair=self.bp,
                                       birth_date=date(2026, 11, 9))
        pups = [Subject.objects.create(line=self.line, litter=litter, lab=self.lab,
                                       birth_date=litter.birth_date) for _ in range(n_pups)]
        return litter, pups

    def _post(self, litters, confirm=True):
        data = {'action': 'rollback_litters', ACTION_CHECKBOX_NAME: [lt.pk for lt in litters]}
        if confirm:
            data['post'] = 'yes'
        return self.client.post(self.url, data, follow=True)

    def _indexes(self):
        self.line.refresh_from_db()
        return self.line.litter_autoname_index, self.line.subject_autoname_index

    def _exists(self, objs):
        return [type(o).objects.filter(pk=o.pk).exists() for o in objs]

    def test_confirmation_page(self):
        self.assertEqual(
            [self.litter.name, *map(str, self.pups)], ['L1_L_002', 'L1_0003', 'L1_0004'])
        r = self._post([self.litter], confirm=False)
        self.assertContains(r, 'Yes, delete and roll back')
        self.assertContains(r, 'L1_0004')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)
        self.assertEqual(self._indexes(), (2, 4))

    def test_rollback(self):
        r = self._post([self.litter])
        self.assertContains(r, 'Rolled back the autonumbering')
        self.assertEqual(self._exists([self.litter, *self.pups]), [False] * 3)
        self.assertEqual(self._exists([self.old_litter, *self.old_pups]), [True] * 3)
        self.assertEqual(self._indexes(), (1, 2))
        # The audit trail records the deletions and the change to the line.
        logs = LogEntry.objects.filter(user=self.admin)
        self.assertEqual(sorted(logs.filter(action_flag=DELETION).values_list(
            'object_repr', flat=True)), ['L1_0003', 'L1_0004', 'L1_L_002'])
        self.assertEqual(logs.get(action_flag=CHANGE).object_id, str(self.line.pk))
        # The names are reused.
        litter, pups = self._litter(1)
        self.assertEqual((litter.name, pups[0].nickname), ('L1_L_002', 'L1_0003'))

    def test_rollback_two_litters_one_without_pups(self):
        third, _ = self._litter(0)
        self._post([third, self.litter])
        self.assertEqual(self._exists([third, self.litter]), [False, False])
        self.assertEqual(self._indexes(), (1, 2))

    def test_refused_if_not_most_recent(self):
        r = self._post([self.old_litter], confirm=False)
        self.assertContains(r, 'are not the most recent litters')
        self.assertNotContains(r, 'Yes, delete and roll back')
        # A forged confirmation is refused too.
        r = self._post([self.old_litter])
        self.assertContains(r, 'are not the most recent')
        self.assertEqual(self._exists([self.old_litter, *self.old_pups]), [True] * 3)
        self.assertEqual(self._indexes(), (2, 4))

    def test_refused_if_pup_renamed(self):
        self.pups[1].nickname = 'special_name'
        self.pups[1].save()
        r = self._post([self.litter])
        self.assertContains(r, 'are not the most recent subjects')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)

    def test_refused_if_pups_are_used(self):
        Weighing.objects.create(subject=self.pups[0], weight=1.2, date_time=timezone.now())
        r = self._post([self.litter])
        self.assertContains(r, 'other records refer to these litters or subjects: weighing')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)
        Weighing.objects.all().delete()
        # A pup that became a breeding pair parent would be detached from it.
        BreedingPair.objects.create(line=self.line, mother1=self.pups[1])
        r = self._post([self.litter])
        self.assertContains(r, 'other records refer to these litters or subjects: breeding pair')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)

    def test_deletion_guard(self):
        # Should a record appear between the check and the deletion, the deletion would take it
        # with the pup; the counts of deleted objects are checked as a last resort.
        Weighing.objects.create(subject=self.pups[0], weight=1.2, date_time=timezone.now())
        plan = subjects_admin.plan_litter_rollback
        with mock.patch.object(subjects_admin, 'plan_litter_rollback',
                               side_effect=lambda litters: (plan(litters)[0], [])):
            r = self._post([self.litter])
        self.assertContains(r, 'would also delete')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)
        self.assertEqual(Weighing.objects.count(), 1)
        self.assertEqual(self._indexes(), (2, 4))
        self.assertFalse(LogEntry.objects.filter(user=self.admin).exists())

    def test_refused_if_pup_has_a_note(self):
        # Notes point at subjects through a generic foreign key, which deletion does not see.
        Note.objects.create(user=self.admin, text='tail tattoo', content_object=self.pups[0])
        r = self._post([self.litter])
        self.assertContains(r, 'other records refer to these litters or subjects: note')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)

    def test_refused_without_line_or_with_pup_of_another_line(self):
        litter = Litter.objects.create(name='no_line', birth_date=date(2026, 11, 9))
        r = self._post([litter])
        self.assertContains(r, 'has no line')
        self.assertTrue(Litter.objects.filter(pk=litter.pk).exists())
        other = Line.objects.create(name='Line two', nickname='L2')
        self.pups[1].line = other
        self.pups[1].save()
        r = self._post([self.litter])
        self.assertContains(r, 'belong to another line')
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)

    def test_rollback_two_lines(self):
        other = Line.objects.create(name='Line two', nickname='L2')
        litter2 = Litter.objects.create(line=other, birth_date=date(2026, 11, 9))
        pup2 = Subject.objects.create(line=other, litter=litter2, lab=self.lab,
                                      birth_date=litter2.birth_date)
        n_revisions = Revision.objects.count()
        r = self._post([self.litter, litter2])
        self.assertContains(r, 'Rolled back the autonumbering of line Line one')
        self.assertContains(r, 'Rolled back the autonumbering of line Line two')
        self.assertEqual(self._exists([self.litter, litter2, pup2]), [False] * 3)
        self.assertEqual(self._indexes(), (1, 2))
        other.refresh_from_db()
        self.assertEqual((other.litter_autoname_index, other.subject_autoname_index), (0, 0))
        # One revision records both lines, and its comment describes both.
        revision = Revision.objects.order_by('-date_created').first()
        self.assertEqual(Revision.objects.count(), n_revisions + 1)
        # (Lines are registered to follow their breeding pairs, so these are saved too.)
        self.assertEqual(sorted(revision.version_set.filter(
            content_type__model='line').values_list('object_repr', flat=True)),
            ['Line one', 'Line two'])
        self.assertIn('Line one', revision.comment)
        self.assertIn('Line two', revision.comment)

    def test_permissions(self):
        # Lab members cannot delete litters or subjects, so the action is not offered.
        self.client.force_login(self.user)
        r = self.client.get(self.url)
        self.assertNotContains(r, 'rollback_litters')
        self._post([self.litter])
        self.assertEqual(self._exists([self.litter, *self.pups]), [True] * 3)
        # Deleting litters is not enough: the subjects are deleted too.
        self.user.user_permissions.add(Permission.objects.get(codename='delete_litter'))
        self.user = LabMember.objects.get(pk=self.user.pk)  # clear the permission cache
        self.assertNotContains(self.client.get(self.url), 'rollback_litters')
        self.user.user_permissions.add(Permission.objects.get(codename='delete_subject'))
        self.assertContains(self.client.get(self.url), 'rollback_litters')
        self.user.user_permissions.clear()
        # Stock managers look after the colony, so they can.
        self.user.is_stock_manager = True
        self.user.save()
        self.assertContains(self.client.get(self.url), 'rollback_litters')
        self._post([self.litter])
        self.assertEqual(self._exists([self.litter, *self.pups]), [False] * 3)


class TestBreedingPairAdmin(TestCase):
    fixtures = ['misc.lab.json']

    def setUp(self):
        self.site = AdminSite()
        setup_admin_subject_user(self)
        self.stock_manager = LabMember.objects.create_user(
            username='stock_manager', password='bar123', email='foo@example.com',
            is_staff=True, is_active=True, is_stock_manager=True)
        kwargs_subjects = dict(
            birth_date=date(2025, 1, 1), lab=self.lab, responsible_user=self.stock_manager)
        self.line = Line.objects.create(nickname='line')
        self.father = Subject.objects.create(nickname='father', sex='M', **kwargs_subjects)
        self.mother1 = Subject.objects.create(nickname='mother1', sex='F', **kwargs_subjects)
        self.breeding_pair = BreedingPair.objects.create(
            line=self.line, father=self.father, mother1=self.mother1, mother2=None)

    def _form_data(self):
        bp = self.breeding_pair
        return {
            'json': bp.json, 'description': bp.description, 'name': bp.name, 'line': bp.line,
            'start_date': bp.start_date, 'end_date': bp.end_date,
            'father': bp.father, 'mother1': bp.mother1, 'mother2': bp.mother2,
        }

    def _assert_parents_kept(self):
        """Check the breeding pair form and line inline both keep the current parents."""
        form = BreedingPairAdminForm(data=self._form_data(), instance=self.breeding_pair)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['father'], self.father)
        self.assertEqual(form.cleaned_data['mother1'], self.mother1)
        # A new breeding pair cannot select excluded subjects
        new_form = BreedingPairAdminForm()
        self.assertNotIn(self.father, new_form.fields['father'].queryset)
        # The line page breeding pair inline must keep them too
        inline = BreedingPairInline(Line, self.site)
        inline._parent_instance = self.line
        for name, parent in (('father', self.father), ('mother1', self.mother1)):
            field = inline.formfield_for_foreignkey(
                BreedingPair._meta.get_field(name), MagicMock())
            self.assertIn(parent, field.queryset)

    def test_set_end_date_with_culled_subject(self):
        # the form is valid as both parents are alive
        form = BreedingPairAdminForm(data=self._form_data(), instance=self.breeding_pair)
        self.assertTrue(form.is_valid())
        # once the father is culled it can't be set on a new breeding pair,
        # but it remains on this one and the form is valid
        Cull.objects.create(subject=self.father, user=self.stock_manager, date=date(2025, 6, 1))
        self.father.refresh_from_db()
        self.assertFalse(self.father.alive())
        self._assert_parents_kept()

    def test_parent_no_longer_stock_managed(self):
        """Parents handed to a non-stock-manager must not be unset from the pair."""
        self.father.responsible_user = self.user  # not a stock manager
        self.father.save()
        self._assert_parents_kept()


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
