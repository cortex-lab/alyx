from unittest.mock import MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.admin.sites import AdminSite

from misc.models import LabMember, Lab
from misc.management.commands.set_user_permissions import Command
from misc.admin import LabAdmin


class TestLabAdminViews(TestCase):

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

    @override_settings(TIME_ZONE='Africa/Djibouti')
    def test_admin_add_form_view(self):
        """Test the lab add form view."""
        response = self.client.get('/admin/misc/lab/add/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.login(username='admin', password='admin')
        response = self.client.get('/admin/misc/lab/add/', follow=True)
        self.assertEqual(response.status_code, 200)
        la = LabAdmin(model=Lab, admin_site=AdminSite())
        request = MagicMock()
        request.user = self.user
        LabForm = la.get_form(request)
        # Check initial value of timezone field
        form = LabForm(data={})
        initial = form.fields['timezone'].initial
        if callable(initial):
            initial = initial()
        self.assertEqual(initial, 'Africa/Djibouti')
        # Check form cleaning
        data = {
            'timezone': 'Africa/Djibouti',
            'name': 'TestLab',
            'reference_weight_pct': 0.8,
            'zscore_weight_pct': 0
        }
        form = LabForm(data=data)
        self.assertTrue(form.is_valid())
        data['timezone'] = 'Africa/Zaire'  # Invalid timezone
        form = LabForm(data=data)
        self.assertFalse(form.is_valid())
        error = form.errors.get('timezone')[0]
        self.assertIn('Time Zone is incorrect. Here is the list', error)
