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


class TestDataNoticeAdminDatasetsField(TestCase):
	"""The datasets M2M is read-only on the change form (it does not scale as a widget)."""

	fixtures = ['misc.lab.json']

	def setUp(self):
		setup_admin_subject_user(self)
		self.site = AdminSite()
		self.factory = RequestFactory()
		self.model_admin = DataNoticeAdmin(DataNotice, self.site)
		self.notice = DataNotice.objects.create(name='admin-datasets-notice', created_by=self.user)
		session = Session.objects.create(subject=self.subject, start_time=timezone.now(), number=1)
		self.datasets = [
			Dataset.objects.create(
				name='notice-datasets-%i.npy' % i, collection='alf', session=session)
			for i in range(3)]
		self.notice.datasets.add(*self.datasets)

	def _request(self):
		request = self.factory.get('/admin/data/datanotice/')
		request.user = self.user
		return request

	def test_datasets_editable_on_add_only(self):
		"""The M2M widget is available when adding a notice but not when changing one."""
		request = self._request()
		self.assertIn('datasets', self.model_admin.get_fields(request))
		change_fields = self.model_admin.get_fields(request, self.notice)
		self.assertNotIn('datasets', change_fields)
		self.assertIn('datasets_', change_fields)
		self.assertIn('datasets_', self.model_admin.get_readonly_fields(request, self.notice))
		# No form field means no per-dataset POST parameters, which would return a 400 status
		form = self.model_admin.get_form(request, obj=self.notice)
		self.assertNotIn('datasets', form.base_fields)
		self.assertIn('datasets', self.model_admin.get_form(request).base_fields)

	def test_datasets_display(self):
		"""The read-only field lists a capped number of datasets in a scrollable box."""
		self.model_admin.max_datasets_displayed = 2
		notice = self.model_admin.get_queryset(self._request()).get(pk=self.notice.pk)
		html = self.model_admin.datasets_(notice)

		self.assertEqual(2, html.count('<li>'), 'expected the dataset list to be truncated')
		self.assertIn('3 datasets attached (showing the first 2)', html)
		self.assertIn('overflow: auto', html, 'expected a scrollable bounding box')
		self.assertIn('?data_notices__id__exact=%s' % self.notice.pk, html)
		self.assertIn('aQt/', html, 'expected the session in the dataset label')
		self.assertIn('alf/notice-datasets-0.npy', html)

	def test_datasets_display_empty(self):
		notice = DataNotice.objects.create(name='admin-empty-notice', created_by=self.user)
		notice = self.model_admin.get_queryset(self._request()).get(pk=notice.pk)
		self.assertEqual('No datasets', self.model_admin.datasets_(notice))

	def test_dataset_count_annotation(self):
		notice = self.model_admin.get_queryset(self._request()).get(pk=self.notice.pk)
		self.assertEqual(3, self.model_admin.dataset_count(notice))

	def test_change_view_save_keeps_datasets(self):
		"""Saving the change form must succeed and leave the dataset list untouched."""
		url = '/admin/data/datanotice/%s/change/' % self.notice.pk
		response = self.client.get(url)
		self.assertEqual(200, response.status_code)
		self.assertNotIn('id_datasets', response.content.decode())

		response = self.client.post(url, data={
			'name': 'admin-datasets-notice-renamed',
			'description': 'why the data are affected',
			'importance': str(DataNotice.IMPORTANCE.MAJOR),
			'version_affected': '',
			'affected_date_start': '',
			'affected_date_end': '',
			'created_by': str(self.user.pk),
			'json': 'null',
			'_save': 'Save',
		})
		self.assertEqual(302, response.status_code, 'change form failed to save')
		self.notice.refresh_from_db()
		self.assertEqual('admin-datasets-notice-renamed', self.notice.name)
		self.assertCountEqual(self.datasets, self.notice.datasets.all())
