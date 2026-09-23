"""Tests for public self-registration and for hiding accounts from public users."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from unittest import mock

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from misc.signup import antibot, preferences
from misc.signup.forms import PUBLIC_GROUP_NAME, signup_token_generator
from misc.management.commands.set_public_permissions import (
    Command as SetPublicPermissions, EXCLUDED_MODELS)

# The bot protection is switched off explicitly rather than left to whatever the settings
# happen to carry: a deployment with real Turnstile keys would otherwise reject every sign-up
# posted here, since a test client has no widget to answer the challenge with.
PUBLIC = dict(ROOT_URLCONF='misc.tests_urls', PUBLIC_DATABASE=True,
              TURNSTILE_SITE_KEY='', TURNSTILE_SECRET_KEY='', PUBLIC_SIGNUP_THROTTLE=None)


@override_settings(**PUBLIC)
class TestSignUp(TestCase):

    def _signup(self, **overrides):
        data = {'username': 'newcomer', 'email': 'newcomer@example.org',
                'password1': 'a-long-enough-passphrase', 'password2': 'a-long-enough-passphrase'}
        data.update(overrides)
        return self.client.post(reverse('signup'), data)

    def test_signup_creates_inactive_public_account(self):
        response = self._signup()
        self.assertRedirects(response, reverse('signup-done'))
        user = get_user_model().objects.get(username='newcomer')
        self.assertTrue(user.is_public_user, 'must be read-only')
        self.assertTrue(user.is_staff, 'needs staff status to browse the admin')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_stock_manager)
        self.assertFalse(user.is_active, 'must confirm email before the account works')
        self.assertEqual([PUBLIC_GROUP_NAME], [g.name for g in user.groups.all()])
        # The password must have been hashed, not stored as given
        self.assertNotEqual('a-long-enough-passphrase', user.password)
        self.assertTrue(user.check_password('a-long-enough-passphrase'))

    def test_signup_sends_confirmation_that_activates(self):
        self._signup()
        user = get_user_model().objects.get(username='newcomer')
        self.assertEqual(1, len(mail.outbox))
        self.assertIn('newcomer@example.org', mail.outbox[0].to)

        url = reverse('signup-verify', kwargs=self._token_kwargs(user))
        response = self.client.get(url)
        self.assertTrue(response.context['verified'])
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_confirmation_link_dies_once_the_account_has_been_used(self):
        """A used link must not be replayable to undo an administrator disabling an account."""
        self._signup()
        user = get_user_model().objects.get(username='newcomer')
        url = reverse('signup-verify', kwargs=self._token_kwargs(user))
        self.assertTrue(self.client.get(url).context['verified'])

        self.assertTrue(self.client.login(
            username='newcomer', password='a-long-enough-passphrase'))
        self.client.logout()

        # Logging in sets last_login, which the token hashes, so the original link is now dead
        # and disabling the account cannot be undone with it.
        user.refresh_from_db()
        user.is_active = False
        user.save()
        self.assertFalse(self.client.get(url).context['verified'])
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_verify_rejects_bad_token(self):
        self._signup()
        user = get_user_model().objects.get(username='newcomer')
        kwargs = self._token_kwargs(user)
        kwargs['token'] = kwargs['token'][:-4] + 'zzzz'
        self.assertFalse(self.client.get(reverse('signup-verify', kwargs=kwargs)).context[
            'verified'])
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_verify_will_not_activate_a_staff_account(self):
        """The token would not validate anyway; this covers the explicit guard in the view."""
        staff = get_user_model().objects.create_user(
            username='curator', password='x', email='c@example.org', is_active=False)
        kwargs = self._token_kwargs(staff)
        self.assertFalse(self.client.get(reverse('signup-verify', kwargs=kwargs)).context[
            'verified'])
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)

    @staticmethod
    def _token_kwargs(user):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        return {'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': signup_token_generator.make_token(user)}

    def test_duplicate_username_and_email_rejected(self):
        get_user_model().objects.create_user(
            username='taken', password='x', email='Taken@Example.org')
        self.assertFormError(
            self._signup(username='taken').context['form'], 'username',
            ['A user with that username already exists.'])
        # Email uniqueness is not enforced by AbstractUser, so the form must do it, and it must
        # be case insensitive or the same address can register repeatedly.
        response = self._signup(email='taken@example.org')
        self.assertIn('email', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='newcomer').exists())

    def test_reserved_username_rejected(self):
        with override_settings(PUBLIC_SIGNUP_RESERVED_USERNAMES=('root', 'intbrainlab')):
            response = self._signup(username='IntBrainLab')  # reserved check is case insensitive
            self.assertIn('username', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='IntBrainLab').exists())

    @override_settings(PUBLIC_SIGNUP_REQUIRE_VERIFICATION=False)
    def test_signup_without_verification_is_active_immediately(self):
        self._signup()
        self.assertTrue(get_user_model().objects.get(username='newcomer').is_active)
        self.assertEqual(0, len(mail.outbox))

    @override_settings(PUBLIC_DATABASE=False)
    def test_signup_unavailable_on_an_internal_database(self):
        """Even if the URLs are routed, the views refuse when the setting is off."""
        self.assertEqual(404, self.client.get(reverse('signup')).status_code)
        self.assertEqual(404, self._signup().status_code)
        self.assertFalse(get_user_model().objects.filter(username='newcomer').exists())


class TestAnonymousAdminLogin(TestCase):
    """The login page is rendered for users who are not logged in yet.

    django.contrib.admin builds its app list while rendering it, calling has_module_permission
    on every registered ModelAdmin with an AnonymousUser - which has none of the LabMember
    fields. Any permission override that reads one directly takes the login page down, for
    every deployment, whether or not it is public.
    """

    def test_login_page_renders_for_anonymous_users(self):
        self.assertEqual(200, self.client.get('/admin/login/').status_code)

    @override_settings(**PUBLIC)
    def test_login_page_renders_on_a_public_database(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(200, response.status_code)
        self.assertContains(response, reverse('signup'))


@override_settings(**PUBLIC)
class TestBotProtection(TestCase):
    """The honeypot and volume cap, and that neither inconveniences a real person."""

    def _post(self, **extra):
        data = {'username': 'newcomer', 'email': 'newcomer@example.org',
                'password1': 'a-long-enough-passphrase', 'password2': 'a-long-enough-passphrase'}
        data.update(extra)
        return self.client.post(reverse('signup'), data)

    def test_honeypot_field_is_present_but_hidden(self):
        response = self.client.get(reverse('signup'))
        self.assertContains(response, antibot.HONEYPOT_FIELD)
        self.assertContains(response, 'aria-hidden="true"')

    def test_completed_honeypot_is_rejected(self):
        response = self._post(**{antibot.HONEYPOT_FIELD: 'http://spam.example'})
        self.assertEqual(200, response.status_code)  # redisplayed, not created
        self.assertFalse(get_user_model().objects.filter(username='newcomer').exists())

    def test_rejection_does_not_name_the_honeypot(self):
        """A bot that learns which field caught it simply stops filling that field in."""
        body = self._post(**{antibot.HONEYPOT_FIELD: 'x'}).content.decode()
        self.assertNotIn('%s field' % antibot.HONEYPOT_FIELD, body)

    def test_empty_honeypot_lets_a_person_through(self):
        self.assertRedirects(self._post(), reverse('signup-done'))

    @override_settings(PUBLIC_SIGNUP_THROTTLE=None)
    def test_throttle_off_by_default(self):
        """Courses and workshops register ~100 people from one address; the default must not
        stand in the way of that."""
        request = RequestFactory().post('/signup', REMOTE_ADDR='10.0.0.1')
        for _ in range(150):
            self.assertFalse(antibot.throttle_exceeded(request))

    @override_settings(PUBLIC_SIGNUP_THROTTLE=(3, 3600))
    def test_throttle_caps_one_address_when_configured(self):
        request = RequestFactory().post('/signup', REMOTE_ADDR='10.0.0.2')
        self.assertEqual([False, False, False, True],
                         [antibot.throttle_exceeded(request) for _ in range(4)])

    @override_settings(PUBLIC_SIGNUP_THROTTLE=(1, 3600),
                       PUBLIC_SIGNUP_THROTTLE_EXEMPT=('10.0.0.3',))
    def test_exempt_address_is_never_throttled(self):
        request = RequestFactory().post('/signup', REMOTE_ADDR='10.0.0.3')
        for _ in range(20):
            self.assertFalse(antibot.throttle_exceeded(request))

    @override_settings(PUBLIC_SIGNUP_THROTTLE=(1, 3600))
    def test_throttled_post_returns_429_and_creates_nothing(self):
        self._post(username='first', email='first@example.org')
        response = self._post(username='second', email='second@example.org')
        self.assertEqual(429, response.status_code)
        self.assertFalse(get_user_model().objects.filter(username='second').exists())

    def test_forwarded_for_ignored_unless_trusted(self):
        """Otherwise a client spoofs the header and the cap counts a different address."""
        request = RequestFactory().post('/signup', REMOTE_ADDR='10.0.0.4',
                                        HTTP_X_FORWARDED_FOR='1.2.3.4')
        self.assertEqual('10.0.0.4', antibot.client_ip(request))
        with override_settings(PUBLIC_SIGNUP_TRUST_FORWARDED_FOR=True):
            self.assertEqual('1.2.3.4', antibot.client_ip(request))


class TestSignUpUrlsNotRouted(TestCase):
    def test_signup_not_routed_by_default(self):
        """With PUBLIC_DATABASE unset, /signup is not part of the URLconf at all.

        The URLconf settles this when it is imported, so the module is reloaded under the
        setting rather than the live URLconf being probed: on a public deployment that URLconf
        routes /signup quite correctly, and the test would be measuring the deployment instead
        of the code.
        """
        import importlib
        from django.urls import clear_url_caches
        from misc import urls as misc_urls

        def routed():
            names = set()
            for pattern in misc_urls.urlpatterns:
                names.add(getattr(pattern, 'name', None))
            return names

        try:
            with override_settings(PUBLIC_DATABASE=False):
                importlib.reload(misc_urls)
                clear_url_caches()
                self.assertNotIn('signup', routed())
            with override_settings(PUBLIC_DATABASE=True):
                importlib.reload(misc_urls)
                clear_url_caches()
                self.assertIn('signup', routed(), 'the check must not pass vacuously')
        finally:
            importlib.reload(misc_urls)
            clear_url_caches()


    def test_routes_load_when_the_flags_are_absent_entirely(self):
        """A settings file that predates these flags must still import.

        The openalyx release container supplies its own settings module and defines neither
        flag; so may any lab running Alyx off the shelf. Importing the names directly made that
        an ImportError at URLconf load, which takes down the site and every manage.py command
        with it - including the migrate step of a release.
        """
        import importlib
        from django.conf import settings as django_settings
        from django.urls import clear_url_caches
        from misc import urls as misc_urls

        absent = {k: getattr(django_settings, k, None)
                  for k in ('PUBLIC_DATABASE', 'SSO_ENABLED')}
        try:
            for key in absent:
                # Both copies: LazySettings caches each value in its own __dict__ on first
                # access, so removing it from the wrapped Settings alone changes nothing.
                django_settings.__dict__.pop(key, None)
                if hasattr(django_settings._wrapped, key):
                    delattr(django_settings._wrapped, key)
            importlib.reload(misc_urls)  # must not raise
            clear_url_caches()
            self.assertNotIn('signup', {getattr(p, 'name', None) for p in misc_urls.urlpatterns})
        finally:
            for key, value in absent.items():
                if value is not None:
                    setattr(django_settings._wrapped, key, value)
                django_settings.__dict__.pop(key, None)
            importlib.reload(misc_urls)
            clear_url_caches()


class TestPublicPermissionsGroup(TestCase):

    def test_group_has_view_permissions_only(self):
        SetPublicPermissions().handle(database='default')
        group = Group.objects.get(name=PUBLIC_GROUP_NAME)
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertTrue(codenames, 'group should not be empty')
        self.assertTrue(all(c.startswith('view_') for c in codenames),
                        'group must not grant add/change/delete')

    def test_group_excludes_accounts_and_permission_structure(self):
        SetPublicPermissions().handle(database='default')
        group = Group.objects.get(name=PUBLIC_GROUP_NAME)
        granted = set(group.permissions.values_list('id', flat=True))
        for app_label, model in EXCLUDED_MODELS:
            excluded = Permission.objects.filter(
                content_type__app_label=app_label, content_type__model=model)
            self.assertFalse(granted & set(excluded.values_list('id', flat=True)),
                             f'{app_label}.{model} must not be viewable by public users')

    def test_set_user_permissions_skips_public_users(self):
        from misc.management.commands.set_user_permissions import Command as SetUserPermissions
        public = get_user_model().objects.create(
            username='member-of-public', is_public_user=True, is_active=False)
        staff = get_user_model().objects.create(username='researcher')

        SetUserPermissions().handle()

        public.refresh_from_db()
        staff.refresh_from_db()
        # Adding a public user to Lab members would give a member of the public write access,
        # and forcing is_active would activate an account that never confirmed its email.
        self.assertEqual([], list(public.groups.all()))
        self.assertFalse(public.is_active)
        self.assertEqual(['Lab members'], [g.name for g in staff.groups.all()])
        self.assertTrue(staff.is_active)


@override_settings(**PUBLIC)
class TestAccountVisibility(TestCase):
    """Public users must not be able to enumerate other people's accounts."""

    def setUp(self):
        self.anonymised = get_user_model().objects.create(
            username='a1b2c3d4', is_active=False)
        self.researcher = get_user_model().objects.create_user(
            username='researcher', password='x', email='researcher@example.org')
        self.public = get_user_model().objects.create_user(
            username='member-of-public', password='x', email='public@example.org',
            is_public_user=True, is_staff=True)
        SetPublicPermissions().handle(database='default')
        self.public.groups.add(Group.objects.get(name=PUBLIC_GROUP_NAME))

    def test_rest_user_list_shows_only_self(self):
        self.client.force_login(self.public)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(200, response.status_code)
        results = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(['member-of-public'], [u['username'] for u in results])

    def test_rest_user_list_unrestricted_for_staff(self):
        self.client.force_login(self.researcher)
        results = self.client.get(reverse('user-list')).data
        results = results['results'] if isinstance(results, dict) else results
        self.assertEqual({'a1b2c3d4', 'researcher', 'member-of-public'},
                         {u['username'] for u in results})

    def test_rest_user_detail_of_another_account_is_not_found(self):
        self.client.force_login(self.public)
        for username in ('researcher', 'a1b2c3d4'):
            self.assertEqual(
                404, self.client.get(reverse('user-list') + '/' + username).status_code)
        self.assertEqual(
            200, self.client.get(reverse('user-list') + '/member-of-public').status_code)

    def test_work_of_anonymised_users_stays_queryable(self):
        """Hiding the user records must not hide the data attributed to them.

        This is what makes it acceptable for public users to lose sight of the user table: the
        usernames are still carried on the data and are still what the filters match on.
        """
        from subjects.models import Subject
        Subject.objects.create(nickname='mouse-1', responsible_user=self.anonymised)
        self.client.force_login(self.public)
        results = self.client.get(
            reverse('subject-list') + '?responsible_user=a1b2c3d4').data
        results = results['results'] if isinstance(results, dict) else results
        self.assertEqual(['mouse-1'], [s['nickname'] for s in results])
        self.assertEqual('a1b2c3d4', results[0]['responsible_user'])

    def test_admin_labmember_hidden_from_public_users(self):
        self.client.force_login(self.public)
        response = self.client.get('/admin/misc/labmember/')
        self.assertIn(response.status_code, (302, 403),
                      'public users must not reach the user changelist')
        # And the model is absent from the admin index
        self.assertNotContains(self.client.get('/admin/'), '/admin/misc/labmember/')

    def test_admin_labmember_visible_to_staff(self):
        self.researcher.is_staff = self.researcher.is_superuser = True
        self.researcher.save()
        self.client.force_login(self.researcher)
        self.assertEqual(200, self.client.get('/admin/misc/labmember/').status_code)


IBL_PREFERENCES = {'data_releases': 'Email me when new data is released',
                   'surveys': 'Email me occasional surveys about how the data is used'}


@override_settings(**PUBLIC, EMAIL_PREFERENCES=IBL_PREFERENCES)
class TestEmailPreferences(TestCase):
    """Email preferences live in LabMember.json; consent is opt-in."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ada', password='x', email='ada@example.org')

    def test_unset_preferences_read_as_false(self):
        self.assertEqual({k: False for k in IBL_PREFERENCES}, preferences.get(self.user))
        self.assertIsNone(preferences.updated(self.user))

    def test_signup_records_the_boxes_ticked(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newcomer', 'email': 'newcomer@example.org',
            'password1': 'a-long-enough-passphrase', 'password2': 'a-long-enough-passphrase',
            'data_releases': 'on'})
        self.assertRedirects(response, reverse('signup-done'))
        user = get_user_model().objects.get(username='newcomer')
        self.assertTrue(preferences.get(user)['data_releases'])
        self.assertFalse(preferences.get(user)['surveys'], 'unticked must not be consent')
        self.assertIsNotNone(preferences.updated(user), 'the time of consent must be recorded')

    def test_signup_without_ticking_stores_no_consent(self):
        self.client.post(reverse('signup'), {
            'username': 'quiet', 'email': 'quiet@example.org',
            'password1': 'a-long-enough-passphrase', 'password2': 'a-long-enough-passphrase'})
        user = get_user_model().objects.get(username='quiet')
        self.assertFalse(any(preferences.get(user).values()))

    def test_page_updates_preferences_and_email(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('preferences'), {
            'email': 'new@example.org', 'surveys': 'on'})
        self.assertRedirects(response, reverse('me'))
        self.user.refresh_from_db()
        self.assertEqual('new@example.org', self.user.email)
        self.assertTrue(preferences.get(self.user)['surveys'])

    def test_an_address_is_required_to_receive_mail(self):
        """An account with no email - an ORCiD one, say - cannot opt in without adding one."""
        self.user.email = ''
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('preferences'), {'email': '', 'data_releases': 'on'})
        self.assertEqual(200, response.status_code)
        self.assertFalse(preferences.get(self.user)['data_releases'])

    def test_an_address_already_in_use_is_refused(self):
        get_user_model().objects.create_user(username='bob', password='x', email='b@example.org')
        self.client.force_login(self.user)
        response = self.client.post(reverse('preferences'), {'email': 'b@example.org'})
        self.assertEqual(200, response.status_code)
        self.user.refresh_from_db()
        self.assertEqual('ada@example.org', self.user.email)

    def test_unknown_keys_are_not_stored(self):
        preferences.set(self.user, {'data_releases': True, 'evil': True})
        self.assertNotIn('evil', self.user.json['email_preferences'])

    def test_the_page_requires_login(self):
        response = self.client.get(reverse('preferences'))
        self.assertEqual(302, response.status_code)
        self.assertIn(reverse('admin:login'), response.url)

    def test_a_change_keeps_the_previous_value(self):
        """Consent has to be demonstrable after the fact, so each change records what it was."""
        preferences.set(self.user, {'data_releases': True})
        self.assertEqual([], preferences.history(self.user, 'data_releases'))
        preferences.set(self.user, {'data_releases': False})
        was = preferences.history(self.user, 'data_releases')
        self.assertEqual([True], [x['value'] for x in was])
        self.assertTrue(was[0]['date_time'], 'the time of the change must be recorded')

    def test_setting_the_same_value_adds_no_history(self):
        preferences.set(self.user, {'data_releases': True})
        preferences.set(self.user, {'data_releases': True})
        self.assertEqual([], preferences.history(self.user, 'data_releases'))

    def test_rest_cannot_write_the_json_field(self):
        """The field is editable=False, so no serialiser or form can be talked into taking it."""
        from misc.serializers import UserSerializer
        self.assertNotIn('json', UserSerializer().get_fields())
        serializer = UserSerializer(
            self.user, data={'json': {'email_preferences': {'data_releases': True}}},
            partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertFalse(preferences.get(self.user)['data_releases'])

    def test_the_admin_form_cannot_write_it_either(self):
        """LabMemberAdminForm uses fields='__all__', so only editable=False keeps json out."""
        from subjects.admin import LabMemberAdminForm
        self.assertNotIn('json', LabMemberAdminForm.base_fields)

    def test_a_new_address_needs_confirming(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        self.assertRedirects(response, reverse('me'))
        self.user.refresh_from_db()
        self.assertFalse(preferences.email_verified(self.user))
        self.assertEqual(1, len(mail.outbox))
        self.assertIn('new@example.org', mail.outbox[0].to)

    def test_the_link_confirms_the_address(self):
        self.client.force_login(self.user)
        self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        self.user.refresh_from_db()
        url = reverse('email-verify', kwargs=self._email_token_kwargs(self.user))
        self.assertTrue(self.client.get(url).context['verified'])
        self.user.refresh_from_db()
        self.assertTrue(preferences.email_verified(self.user))

    def test_changing_the_address_again_kills_the_link(self):
        """The token hashes the address, so a link cannot confirm one since moved away from."""
        self.client.force_login(self.user)
        self.client.post(reverse('preferences'), {'email': 'first@example.org'})
        self.user.refresh_from_db()
        stale = reverse('email-verify', kwargs=self._email_token_kwargs(self.user))
        self.client.post(reverse('preferences'), {'email': 'second@example.org'})
        self.assertFalse(self.client.get(stale).context['verified'])
        self.user.refresh_from_db()
        self.assertFalse(preferences.email_verified(self.user))

    def test_another_user_cannot_confirm_it(self):
        self.client.force_login(self.user)
        self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        self.user.refresh_from_db()
        url = reverse('email-verify', kwargs=self._email_token_kwargs(self.user))
        other = get_user_model().objects.create_user(
            username='mallory', password='x', email='m@example.org')
        self.client.force_login(other)
        self.assertFalse(self.client.get(url).context['verified'])
        self.user.refresh_from_db()
        self.assertFalse(preferences.email_verified(self.user))

    def test_a_confirmed_address_is_not_mailed_again(self):
        preferences.set_email_verified(self.user, True)
        self.client.force_login(self.user)
        self.client.post(reverse('preferences'),
                         {'email': self.user.email, 'data_releases': 'on'})
        self.assertEqual(0, len(mail.outbox))
        self.user.refresh_from_db()
        self.assertTrue(preferences.get(self.user)['data_releases'])

    def test_saving_a_preference_keeps_the_address_confirmed(self):
        """set() rebuilds the stored dict, so it has to carry the verified flag through."""
        preferences.set_email_verified(self.user, True)
        preferences.set(self.user, {'data_releases': True})
        self.user.refresh_from_db()
        self.assertTrue(preferences.email_verified(self.user))

    def test_saving_again_while_unconfirmed_sends_another_link(self):
        """What the page tells the user to do to get a fresh link."""
        self.client.force_login(self.user)
        self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        mail.outbox.clear()
        self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        self.assertEqual(1, len(mail.outbox))
        self.assertIn('new@example.org', mail.outbox[0].to)

    def test_a_failed_send_leaves_the_account_alone(self):
        """Unlike sign-up, the mail is not what makes the account work, so nothing is undone."""
        self.client.force_login(self.user)
        with mock.patch('misc.signup.views.send_mail', side_effect=Exception('boom')):
            response = self.client.post(reverse('preferences'), {'email': 'new@example.org'})
        self.assertEqual(200, response.status_code)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    @staticmethod
    def _email_token_kwargs(user):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from misc.signup.forms import email_change_token_generator
        return {'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': email_change_token_generator.make_token(user)}

@override_settings(**PUBLIC, EMAIL_PREFERENCES={})
class TestEmailPreferencesUnconfigured(TestCase):
    """With no EMAIL_PREFERENCES the feature is absent, as it is for an internal lab database.

    Overridden explicitly rather than left to the ambient settings: a public deployment
    configures options, and the test would then be measuring the deployment.
    """

    def test_no_options_offered(self):
        self.assertEqual({}, preferences.options())

    def test_signup_form_has_no_checkboxes(self):
        from misc.signup.forms import PublicSignUpForm
        fields = PublicSignUpForm().fields
        self.assertNotIn('data_releases', fields)

    def test_the_page_is_not_routed(self):
        import importlib
        from django.urls import clear_url_caches
        from misc import urls as misc_urls
        try:
            importlib.reload(misc_urls)
            clear_url_caches()
            self.assertNotIn(
                'preferences', {getattr(p, 'name', None) for p in misc_urls.urlpatterns})
        finally:
            importlib.reload(misc_urls)
            clear_url_caches()


@override_settings(**PUBLIC, EMAIL_PREFERENCES=IBL_PREFERENCES)
class TestAccountPageVerification(TestCase):
    """The account page flags an address that has not been confirmed."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ada', password='x', email='ada@example.org')
        self.client.force_login(self.user)

    def test_unconfirmed_is_flagged(self):
        response = self.client.get(reverse('me'))
        self.assertContains(response, 'not confirmed')

    def test_confirmed_is_not_flagged(self):
        preferences.set_email_verified(self.user, True)
        response = self.client.get(reverse('me'))
        self.assertNotContains(response, 'not confirmed')

    def test_no_address_is_not_flagged(self):
        self.user.email = ''
        self.user.save()
        response = self.client.get(reverse('me'))
        self.assertNotContains(response, 'not confirmed')

    @override_settings(EMAIL_PREFERENCES={})
    def test_nothing_flagged_where_the_feature_is_off(self):
        """No confirmation flow exists there, so the flag would be noise."""
        response = self.client.get(reverse('me'))
        self.assertNotContains(response, 'not confirmed')
