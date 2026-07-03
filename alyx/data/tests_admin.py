"""Tests for data admin pages."""

from django.utils import timezone
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from actions.models import Session
from alyx.test_base import setup_admin_subject_user
from data.admin import DataNoticeAdmin
from data.models import DataNotice, Dataset, Tag
from subjects.models import Project


class TestDataNoticeAdminDatasetTagFilter(TestCase):
	fixtures = ['misc.lab.json']

	def setUp(self):
		setup_admin_subject_user(self)
		self.site = AdminSite()
		self.factory = RequestFactory()
		self.model_admin = DataNoticeAdmin(DataNotice, self.site)

	def _make_filter(self, query_params):
		request = self.factory.get('/admin/data/datanotice/', data=query_params)
		request.user = self.user
		params = request.GET.copy()
		return self.model_admin.DatasetTagListFilter(request, params, DataNotice, self.model_admin)

	def test_dataset_tag_filter_returns_matching_notices(self):
		d1 = Dataset.objects.create(name='notice-tag-admin-1.npy')
		d2 = Dataset.objects.create(name='notice-tag-admin-2.npy')
		public_tag = Tag.objects.create(name='public-tag-admin')
		private_tag = Tag.objects.create(name='private-tag-admin')
		d1.tags.add(public_tag)
		d2.tags.add(private_tag)

		n1 = DataNotice.objects.create(name='admin-tag-notice-a', created_by=self.user)
		n1.datasets.add(d1)
		n2 = DataNotice.objects.create(name='admin-tag-notice-b', created_by=self.user)
		n2.datasets.add(d2)
		n3 = DataNotice.objects.create(name='admin-tag-notice-c', created_by=self.user)
		n3.datasets.add(d1, d2)

		admin_filter = self._make_filter({'dataset_tag': str(public_tag.id)})
		filtered = admin_filter.queryset(None, DataNotice.objects.all())

		names = set(filtered.values_list('name', flat=True))
		self.assertEqual(names, {'admin-tag-notice-a', 'admin-tag-notice-c'})

	def test_project_filter_returns_matching_notices(self):
		project_a = Project.objects.create(name='project-admin-a')
		project_b = Project.objects.create(name='project-admin-b')

		session_a = Session.objects.create(subject=self.subject, start_time=timezone.now())
		session_b = Session.objects.create(subject=self.subject, start_time=timezone.now())
		session_a.projects.add(project_a)
		session_b.projects.add(project_b)

		d1 = Dataset.objects.create(name='notice-project-admin-1.npy', session=session_a)
		d2 = Dataset.objects.create(name='notice-project-admin-2.npy', session=session_b)

		n1 = DataNotice.objects.create(name='admin-project-notice-a', created_by=self.user)
		n1.datasets.add(d1)
		n2 = DataNotice.objects.create(name='admin-project-notice-b', created_by=self.user)
		n2.datasets.add(d2)
		n3 = DataNotice.objects.create(name='admin-project-notice-c', created_by=self.user)
		n3.datasets.add(d1, d2)

		request = self.factory.get('/admin/data/datanotice/', data={'project': str(project_a.id)})
		request.user = self.user
		params = request.GET.copy()
		admin_filter = self.model_admin.SessionProjectListFilter(
			request,
			params,
			DataNotice,
			self.model_admin,
		)
		filtered = admin_filter.queryset(None, DataNotice.objects.all())

		names = set(filtered.values_list('name', flat=True))
		self.assertEqual(names, {'admin-project-notice-a', 'admin-project-notice-c'})
