"""Tests for single sign-on policy, provisioning, and the account page.

The policy functions are tested unconditionally: they take plain values and have no dependency
on django-allauth, so they run wherever Alyx is tested rather than only where the optional
[sso] extra is installed. The adapter tests skip themselves when it is absent.
"""
import unittest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from misc import sso
from misc.forms import PUBLIC_GROUP_NAME
from misc.management.commands.set_public_permissions import Command as SetPublicPermissions


class TestSignInPolicy(TestCase):

    def test_domain_allowlist_off_by_default(self):
        self.assertEqual((True, ''), sso.check_email_domain('anyone@anywhere.org'))

    @override_settings(SSO_ALLOWED_DOMAINS=('example.ac.uk',))
    def test_domain_allowlist(self):
        self.assertEqual((True, ''), sso.check_email_domain('ada@Example.AC.uk'))
        permitted, reason = sso.check_email_domain('eve@elsewhere.com')
        self.assertFalse(permitted)
        self.assertEqual(sso.REJECT_DOMAIN, reason)

    @override_settings(SSO_ALLOWED_DOMAINS=('example.ac.uk',))
    def test_domain_allowlist_permits_an_absent_address(self):
        """ORCID supplies no email, so judging on domain would lock out every one of its users."""
        self.assertEqual((True, ''), sso.check_email_domain(''))

    def test_superuser_refused_by_default(self):
        user = get_user_model()(username='root', is_superuser=True, is_active=True)
        permitted, reason = sso.check_existing_user(user)
        self.assertFalse(permitted)
        self.assertEqual(sso.REJECT_SUPERUSER, reason)

    @override_settings(SSO_ALLOW_SUPERUSER=True)
    def test_superuser_permitted_when_configured(self):
        user = get_user_model()(username='root', is_superuser=True, is_active=True)
        self.assertEqual((True, ''), sso.check_existing_user(user))

    def test_inactive_account_refused(self):
        """An administrator disabling an account must not be undone by signing in again."""
        user = get_user_model()(username='ada', is_active=False)
        permitted, reason = sso.check_existing_user(user)
        self.assertFalse(permitted)
        self.assertEqual(sso.REJECT_INACTIVE, reason)

    def test_active_account_permitted(self):
        self.assertEqual(
            (True, ''), sso.check_existing_user(get_user_model()(username='ada', is_active=True)))


class TestUsernameAllocation(TestCase):
    """Usernames are allocated by allauth; these assert the behaviour Alyx depends on."""

    def setUp(self):
        if sso.DefaultSocialAccountAdapter is None:
            self.skipTest('requires the optional [sso] extra')
        self.adapter = sso.AlyxSocialAccountAdapter()

    def _allocate(self, **claims):
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        login = SocialLogin(user=get_user_model()(username='', email=''),
                            account=SocialAccount(provider='orcid', uid='uid'))
        return self.adapter.populate_user(None, login, claims).username

    def test_derives_a_username_without_an_email(self):
        """ORCID returns a name and no address, so the name is all there is to work from."""
        self.assertEqual('ada_lovelace',
                         self._allocate(first_name='Ada', last_name='Lovelace', email=''))

    def test_suffixes_a_taken_name_without_revealing_a_count(self):
        get_user_model().objects.create(username='ada_lovelace')
        allocated = self._allocate(first_name='Ada', last_name='Lovelace', email='')
        self.assertNotEqual('ada_lovelace', allocated)
        self.assertTrue(allocated.startswith('ada_lovelace'))
        # allauth appends a random suffix rather than a counter, so a username says nothing
        # about how many people share a name.
        self.assertNotEqual('ada_lovelace2', allocated)

    @override_settings(ACCOUNT_USERNAME_BLACKLIST=['root'])
    def test_never_allocates_a_reserved_name(self):
        """A provider may offer any preferred_username; reserved ones must not be taken."""
        self.assertNotEqual('root', self._allocate(username='root', email=''))


class TestProvisioningPolicy(TestCase):

    @override_settings(PUBLIC_DATABASE=True)
    def test_public_database_account_is_read_only_staff(self):
        user = sso.apply_new_user_policy(get_user_model()(username='ada'))
        self.assertTrue(user.is_active, 'the provider has already established who this is')
        self.assertTrue(user.is_public_user)
        self.assertTrue(user.is_staff, 'needed to browse the admin')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_stock_manager)

    @override_settings(PUBLIC_DATABASE=False)
    def test_internal_database_account_has_no_admin_access(self):
        user = sso.apply_new_user_policy(get_user_model()(username='ada'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_public_user)
        self.assertFalse(user.is_staff, 'admin access is for an administrator to grant')

    @override_settings(PUBLIC_DATABASE=True)
    def test_public_group_added_on_a_public_database(self):
        SetPublicPermissions().handle(database='default')
        user = get_user_model().objects.create(username='ada')
        sso.add_new_user_groups(user)
        self.assertEqual([PUBLIC_GROUP_NAME], [g.name for g in user.groups.all()])

    @override_settings(PUBLIC_DATABASE=False, SSO_NEW_USER_GROUPS=('Lab members',))
    def test_configured_groups_applied(self):
        Group.objects.get_or_create(name='Lab members')
        user = get_user_model().objects.create(username='ada')
        sso.add_new_user_groups(user)
        self.assertEqual(['Lab members'], [g.name for g in user.groups.all()])


@unittest.skipIf(sso.DefaultSocialAccountAdapter is None, 'requires the optional [sso] extra')
class TestAdapter(TestCase):
    """The parts that need django-allauth installed."""

    def setUp(self):
        self.adapter = sso.AlyxSocialAccountAdapter()

    @override_settings(SSO_CREATE_USER=False)
    def test_signup_closed_by_default(self):
        self.assertFalse(self.adapter.is_open_for_signup(None, self._sociallogin()))

    @override_settings(SSO_CREATE_USER=True)
    def test_signup_open_when_configured(self):
        self.assertTrue(self.adapter.is_open_for_signup(None, self._sociallogin()))

    def test_username_derived_without_an_email(self):
        """ORCID returns given/family name and no email, so the username comes from the name."""
        user = self.adapter.populate_user(
            None, self._sociallogin(),
            {'first_name': 'Ada', 'last_name': 'Lovelace', 'email': ''})
        self.assertTrue(user.username, 'a username must be derived from something')
        self.assertNotIn('@', user.username)

    def test_username_avoids_reserved_names(self):
        with override_settings(PUBLIC_SIGNUP_RESERVED_USERNAMES=('ada',)):
            user = self.adapter.populate_user(
                None, self._sociallogin(), {'username': 'ada', 'email': ''})
        self.assertNotEqual('ada', user.username)

    @staticmethod
    def _sociallogin(uid='0000-0002-1825-0097', email=''):
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        user = get_user_model()(username='', email=email)
        return SocialLogin(user=user, account=SocialAccount(provider='orcid', uid=uid))


class TestAccountPage(TestCase):
    """The /me page is how a user without a password obtains an API credential."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ada', password='x', email='ada@example.org')

    def test_requires_login(self):
        response = self.client.get(reverse('me'))
        self.assertEqual(302, response.status_code)
        self.assertIn(reverse('admin:login'), response.url)

    def test_creates_and_shows_a_token(self):
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.client.force_login(self.user)
        response = self.client.get(reverse('me'))
        self.assertEqual(200, response.status_code)
        token = Token.objects.get(user=self.user)
        self.assertContains(response, token.key)
        self.assertContains(response, 'ada')

    def test_token_can_be_regenerated(self):
        self.client.force_login(self.user)
        self.client.get(reverse('me'))
        original = Token.objects.get(user=self.user).key
        response = self.client.post(reverse('me'))
        self.assertRedirects(response, reverse('me'))
        self.assertNotEqual(original, Token.objects.get(user=self.user).key)
        self.assertEqual(1, Token.objects.filter(user=self.user).count())

    def test_works_for_an_account_with_no_usable_password(self):
        """The case the page exists for: neither password reset nor change can help these."""
        self.user.set_unusable_password()
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse('me'))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, Token.objects.get(user=self.user).key)
