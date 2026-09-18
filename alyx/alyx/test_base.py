from datetime import date
from pathlib import Path
import json
import tempfile
import uuid

from django.test import Client, RequestFactory, TestCase, override_settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.urls import reverse

from alyx.base import _custom_filter_parser
from alyx.throttling import AdaptiveScopedRateThrottle, IPRateThrottle


class TestDocView(TestCase):

    def test_coreapi_deprecated(self):
        """
        This test is enforcing a deprecation. If you have this failing, you are the lucky winner to
        finish the deprecation of the core-api support from Alyx.
        - remove this full test class
        - in alyx/alyx/views.py remove the custom view SpectacularRedocViewCoreAPIDeprecation. At the time
        of writing these lines, the whole view.py is about this so the whole file can go
        - in alyx/alyx/urls.py set the /api/schema url point to SpectacularRedocView instead of
        SpectacularRedocViewCoreAPIDeprecation
        - remove data/coreapi.json
        - make sure all the tests pass
        :return:
        """
        self.assertGreater(date(2026, 9, 22), date.today())

    def test_coreapi_json_view(self):
        client = Client()
        response = client.get('/docs/', headers={'Accept': 'application/coreapi+json'})
        schema = json.loads(response.text)
        self.assertEqual(schema['brain-regions']['read']['fields'][0]['name'], 'id')


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

    def test_parser_rejects_expressions(self):
        """Bracketed values are parsed as literals; this filter is reachable by any REST user."""
        marker = Path(tempfile.gettempdir(), 'alyx_filter_parser_rce')
        marker.unlink(missing_ok=True)
        payloads = [
            f'f0,[__import__("pathlib").Path("{marker}").touch()]',
            'f0,[1 for _ in ().__class__.__bases__]',
            'f0,(__import__("os").getpid())',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertRaises(ValueError, _custom_filter_parser, payload)
        self.assertFalse(marker.exists(), 'the filter parser executed a call')


class AnonymousAccessTest(TestCase):
    """Routes that must not answer a client that has not signed in.

    /admin-tasks/status was served to anyone, and four REST endpoints never set
    permission_classes, so they inherited DRF's AllowAny default. /api is public on purpose.
    """

    def test_lab_member_pages_redirect_anonymous(self):
        subject_id = uuid.uuid4()
        for url in (reverse('tasks_status'),
                    reverse('training'),
                    reverse('subject-history', args=[subject_id]),
                    reverse('water-history', args=[subject_id])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(302, response.status_code)
                self.assertIn('login', response['Location'])

    def test_rest_endpoints_refuse_anonymous(self):
        for method, url in (('get', reverse('check-protected')),
                            ('get', reverse('sync-file-status')),
                            ('post', reverse('sync-file-status')),
                            ('post', reverse('register-file')),
                            ('post', reverse('new-download'))):
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertIn(response.status_code, (401, 403))

    def test_api_root_is_public(self):
        """Deliberately open: an index and a how-to, and where an agent starts."""
        response = self.client.get(reverse('api-root'))
        self.assertEqual(200, response.status_code)

    def test_weighing_plot_refuses_anonymous(self):
        """Empty body rather than a redirect: this one is embedded in an admin page."""
        response = self.client.get(reverse('weighing-plot', args=[uuid.uuid4()]))
        self.assertEqual(b'', response.content)

    def test_lab_member_pages_refuse_public_user(self):
        """Public accounts are staff, so is_staff alone would let them in."""
        user = get_user_model().objects.create_user(username='pub', password='pw')
        user.is_staff = True
        user.is_public_user = True
        user.save()
        self.client.force_login(user)
        self.assertEqual(403, self.client.get(reverse('tasks_status')).status_code)


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


class DocsIPThrottle(IPRateThrottle):
    scope = 'docs'
    rate = '10/minute'


class TestThrottling(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_ip_rate_throttle_uses_ip_cache_key(self):
        request = self.factory.get('/docs/', REMOTE_ADDR='203.0.113.10')
        request.user = AnonymousUser()
        throttle = DocsIPThrottle()

        key = throttle.get_cache_key(request, view=None)

        self.assertEqual(key, 'throttle_docs_203.0.113.10')

    def test_ip_rate_throttle_returns_none_when_rate_is_disabled(self):
        request = self.factory.get('/docs/', REMOTE_ADDR='203.0.113.10')
        request.user = AnonymousUser()
        throttle = DocsIPThrottle()
        throttle.rate = None

        key = throttle.get_cache_key(request, view=None)

        self.assertIsNone(key)

    @override_settings(THROTTLE_MODE='user-based')
    def test_adaptive_scoped_rate_throttle_uses_user_ident_when_authenticated(self):
        user = get_user_model().objects.create_user('throttle_user', 'throttle@example.com', 'pass')
        request = self.factory.get('/docs/', REMOTE_ADDR='198.51.100.1')
        request.user = user

        throttle = AdaptiveScopedRateThrottle()
        throttle.scope = 'docs'

        key = throttle.get_cache_key(request, view=None)

        self.assertEqual(key, f'throttle_docs_{user.pk}')

    @override_settings(THROTTLE_MODE='anonymous')
    def test_adaptive_scoped_rate_throttle_uses_ip_even_when_authenticated(self):
        user = get_user_model().objects.create_user('throttle_user2', 'throttle2@example.com', 'pass')
        request = self.factory.get('/docs/', REMOTE_ADDR='198.51.100.20')
        request.user = user

        throttle = AdaptiveScopedRateThrottle()
        throttle.scope = 'docs'

        key = throttle.get_cache_key(request, view=None)

        self.assertEqual(key, 'throttle_docs_198.51.100.20')
