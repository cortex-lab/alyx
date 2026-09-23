"""Single sign-on policy and provisioning.

Inert unless a deployment sets SSO_ENABLED (see settings.py for the options, and the single
sign-on section of docs/03_deployment.md for a worked ORCID example). Enabling it also needs
the optional dependency, `pip install alyx[sso]`; `manage.py check` reports it if missing.

Identities are stored by django-allauth in its own tables, keyed on (provider, uid) with a
unique constraint. That pairing is what makes a provider such as ORCID usable: ORCID's OpenID
Connect surface returns no email address at all - `email` appears in neither its scopes nor its
supported claims - so an email address cannot be the thing that identifies a returning user.
An account here may therefore have no email address, and still work for data access.

The policy functions below take plain dictionaries and touch nothing from allauth, so they can
be tested wherever Alyx is tested rather than only where the extra is installed. The adapter at
the bottom is the only part that needs it.
"""
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import AppRegistryNotReady

logger = logging.getLogger(__name__)

# Reasons a sign-in is refused. Logged, never shown to the user, since they describe an account
# the person in front of the browser may not own.
REJECT_DOMAIN = 'this email domain is not permitted to sign in'
REJECT_SUPERUSER = 'superusers may not sign in through SSO'
REJECT_INACTIVE = 'the account is not active'


def _setting(name, default):
    return getattr(settings, name, default)


def configured_app(provider, provider_id=''):
    """The SOCIALACCOUNT_PROVIDERS entry for a provider, whichever shape it uses.

    Named providers such as google or orcid carry a single APP. openid_connect carries APPS, a
    list, because one deployment may talk to several servers; provider_id picks the entry.
    """
    config = (_setting('SOCIALACCOUNT_PROVIDERS', {}) or {}).get(provider) or {}
    apps = list(config.get('APPS') or ())
    if not apps and config.get('APP'):
        apps = [config['APP']]
    if provider_id:
        apps = [app for app in apps if app.get('provider_id') == provider_id]
    return apps[0] if apps else None


def login_url_kwargs():
    """Reverse arguments for the sign-in URL.

    openid_connect routes through the app id rather than the provider name, so its URL cannot
    be reversed without one.
    """
    provider_id = _setting('SSO_PROVIDER_ID', '')
    return {'provider_id': provider_id} if provider_id else {}


def check_email_domain(email):
    """Apply the domain allowlist, if one is configured.

    An empty address passes: a provider that supplies no email cannot be judged on its domain,
    and refusing on that basis would lock out every ORCID user.
    """
    domains = tuple(_setting('SSO_ALLOWED_DOMAINS', ()) or ())
    if not domains or not email:
        return True, ''
    if email.rsplit('@', 1)[-1].lower() in {d.lower() for d in domains}:
        return True, ''
    return False, REJECT_DOMAIN


def check_existing_user(user):
    """Whether an identity may be signed in to an account that already exists.

    Returns (True, '') to allow, else (False, reason).
    """
    if user.is_superuser and not _setting('SSO_ALLOW_SUPERUSER', False):
        return False, REJECT_SUPERUSER
    if not user.is_active:
        return False, REJECT_INACTIVE
    return True, ''


def new_user_groups():
    """Group names given to an account created through SSO."""
    names = set(_setting('SSO_NEW_USER_GROUPS', ()) or ())
    if _setting('PUBLIC_DATABASE', False):
        from .forms import PUBLIC_GROUP_NAME
        names.add(PUBLIC_GROUP_NAME)
    return names


def apply_new_user_policy(user):
    """Set the flags and groups a newly provisioned SSO account should have.

    Staff status is the door to the admin site rather than a permission in itself: an account
    with no groups sees an empty admin. What it can actually do is decided by its groups, which
    is what SSO_NEW_USER_GROUPS and the Public users group are for. The sign-up form grants it
    on the same basis.

    The account is active immediately. The provider has established who this is, which is the
    same thing the sign-up form's confirmation email establishes - and for a provider that
    supplies no email address there is nothing to confirm.
    """
    public = _setting('PUBLIC_DATABASE', False)
    user.is_active = True
    user.is_public_user = public
    user.is_staff = True
    user.is_superuser = False
    user.is_stock_manager = False
    return user


def add_new_user_groups(user):
    groups = Group.objects.filter(name__in=new_user_groups())
    if groups:
        user.groups.add(*groups)
    return user


# The adapter is defined only where allauth is both installed and enabled, so that importing
# this module - and so testing everything above - works either way. Note the app registry check:
# importing allauth's adapter while its apps are absent from INSTALLED_APPS raises RuntimeError
# from Django's model machinery rather than ImportError, which a deployment that has the extra
# installed but SSO switched off would otherwise hit.
try:
    _allauth_enabled = apps.is_installed('allauth.socialaccount')
except AppRegistryNotReady:  # pragma: no cover - only if imported during app loading
    _allauth_enabled = False

if _allauth_enabled:
    from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
else:  # pragma: no cover - exercised where the extra is absent or SSO is off
    DefaultSocialAccountAdapter = None


if DefaultSocialAccountAdapter is not None:

    from allauth.core.exceptions import ImmediateHttpResponse
    from django.contrib import messages
    from django.shortcuts import redirect

    class AlyxSocialAccountAdapter(DefaultSocialAccountAdapter):
        """Applies Alyx's sign-in policy to django-allauth."""

        def is_open_for_signup(self, request, sociallogin):
            """Whether an identity with no account here may create one."""
            if _setting('SSO_CREATE_USER', False):
                return True
            logger.info('Refused SSO sign-up for %s: SSO_CREATE_USER is off',
                        sociallogin.account.uid)
            return False

        def pre_social_login(self, request, sociallogin):
            """Vet the identity before allauth acts on it.

            Runs for both new and returning users, so it is the one place that sees every
            sign-in. Refusal raises ImmediateHttpResponse, which is how allauth expects an
            adapter to abort the flow.
            """
            email = (sociallogin.user.email or '').strip().lower()
            permitted, reason = check_email_domain(email)
            if permitted and sociallogin.is_existing:
                permitted, reason = check_existing_user(sociallogin.user)
            if not permitted:
                logger.warning('Refused SSO sign-in for %s (%s): %s',
                               sociallogin.account.uid, email or 'no email', reason)
                self._abort(request, 'Sign-in was refused. Contact an administrator if you '
                                     'believe this is a mistake.')

        def populate_user(self, request, sociallogin, data):
            """Build the candidate user, allocating a username Alyx is willing to store.

            allauth resolves a clash with a random suffix rather than a counter, so a username
            says nothing about how many people share a name.

            Reserved names are dropped first: a provider may hand over a `preferred_username` of
            "root". The list is read from the same setting the sign-up form honours, so a
            deployment that sets only that one is protected on both paths.
            """
            # allauth's own socialaccount adapter imports it under this alias.
            from allauth.account.adapter import get_adapter as get_account_adapter
            user = super(AlyxSocialAccountAdapter, self).populate_user(
                request, sociallogin, data)
            reserved = {name.casefold() for name in _setting(
                'PUBLIC_SIGNUP_RESERVED_USERNAMES', ())}
            candidates = [
                user.username or data.get('username') or '',
                (data.get('email') or '').split('@')[0],
                ' '.join(filter(None, (data.get('first_name'), data.get('last_name')))),
                'user',
            ]
            candidates = [c for c in candidates if c and c.casefold() not in reserved]
            # generate_unique_username lives on the account adapter, not this one. It needs
            # something to work from, so the last resort survives even a deployment that
            # reserves every name offered here; it will be suffixed if it is taken.
            user.username = get_account_adapter().generate_unique_username(
                candidates or ['user'])
            return user

        def save_user(self, request, sociallogin, form=None):
            """Create the account. Called only for a genuinely new identity."""
            apply_new_user_policy(sociallogin.user)
            # The base implementation sets an unusable password and saves both the user and the
            # SocialAccount that identifies them.
            user = super(AlyxSocialAccountAdapter, self).save_user(request, sociallogin, form)
            add_new_user_groups(user)
            logger.info('Created account %s from %s identity %s',
                        user.username, sociallogin.account.provider, sociallogin.account.uid)
            return user

        @staticmethod
        def _abort(request, message):
            messages.error(request, message)
            raise ImmediateHttpResponse(redirect('admin:login'))
