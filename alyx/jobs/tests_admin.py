from unittest.mock import MagicMock

from django.test import TestCase
from django.test import Client
from django.contrib.admin.sites import AdminSite
from django.forms import fields
# from django.contrib.auth.models import Group, Permission

from misc.models import LabMember, Lab, LabMembership
from subjects.models import Subject
from actions.models import Session
from data.models import DataRepositoryType, DataRepository
from misc.management.commands.set_user_permissions import Command
from jobs.admin import TaskAdmin
from jobs.models import Task


class TestJobsAdminViews(TestCase):
    fixtures = ['data.datarepositorytype.json', 'misc.lab.json']

    def setUp(self):
        self.client = Client()
        self.user = LabMember.objects.create_user(
            username='foo', password='bar123', email='foo@example.com')
        self.user.is_staff = self.user.is_active = True  # used by below Command instance
        self.user.save()

        self.superuser = LabMember.objects.create_superuser(
            username='admin', password='admin', email='admin@example.com')
        Command().handle()  # set user group permissions
        self.client.login(username='foo', password='bar123')
        repo_type = DataRepositoryType.objects.get(name='Fileserver')
        self.repo = DataRepository.objects.create(name='test_repo', repository_type=repo_type)
        self.task = Task.objects.create(
            name='test_task', status=10, level=0, data_repository=self.repo)
        self.lab = Lab.objects.get(name='cortexlab')
        self.lab.repositories.add(self.repo)

    def test_admin_add_form_view(self):
        """Test the task add form view."""
        response = self.client.get('/admin/jobs/task/add/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.login(username='admin', password='admin')
        response = self.client.get('/admin/jobs/task/add/', follow=True)
        self.assertEqual(response.status_code, 200)
        ta = TaskAdmin(model=Task, admin_site=AdminSite())
        self.assertCountEqual(['session', 'log', 'parents'], ta.readonly_fields)
        request = MagicMock()
        request.user = self.user
        form = ta.get_form(request)
        # All model fields should be present in the form except the following
        expected = {'session', 'id', 'datetime', 'log'}
        excluded = {x.name for x in Task._meta.fields} - set(form.base_fields.keys())
        self.assertEqual(expected, excluded)
        self.assertIsInstance(form.base_fields['status'], fields.ChoiceField)
        # response = ta.add_view(request)  # in future we may want to test form submission

    def test_has_change_permission(self):
        """Test the has_change_permission method of the TaskAdmin class."""
        ta = TaskAdmin(model=Task, admin_site=AdminSite())
        request = MagicMock()
        request.user = self.user

        self.assertEqual(18, len(ta.get_fields(request)))
        # Check if the user has permission to change a task
        self.assertFalse(ta.has_change_permission(request))
        self.assertFalse(ta.has_change_permission(request, obj=self.task))
        # Check if the user has permission to change task when member of the same lab
        membership = LabMembership.objects.create(lab=self.lab, user=self.user)
        self.user.lab_id().contains(self.lab)
        self.assertTrue(ta.has_change_permission(request, obj=self.task))
        # Check if the user has permission to change task when user of the task session
        membership.delete()
        subject = Subject.objects.create(nickname='586', lab=self.lab)
        session = Session.objects.create(
            subject=subject, number=1, type='Experiment', task_protocol='foo')
        session.users.add(self.user)
        # Check superuser permissions
        request.user = self.superuser
        self.assertTrue(ta.has_change_permission(request))
