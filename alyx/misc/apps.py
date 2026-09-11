from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Warning, register


class UsersConfig(AppConfig):
    name = 'misc'

    def ready(self):
        register(check_public_signup_settings)
        register(check_sso_settings)


def check_public_signup_settings(app_configs, **kwargs):
    """Warn about a public database whose registration flow cannot actually complete.

    Registration confirmation and password reset are the only ways a public user gets or
    recovers an account, and both are email. Without a backend that sends anything, sign-ups
    silently strand at the unconfirmed stage, so surface it at check time instead.
    """
    errors = []
    if not getattr(settings, 'PUBLIC_DATABASE', False):
        return errors
    inert = ('django.core.mail.backends.console.EmailBackend',
             'django.core.mail.backends.dummy.EmailBackend',
             'django.core.mail.backends.locmem.EmailBackend')
    backend = getattr(settings, 'EMAIL_BACKEND', None)
    if getattr(settings, 'PUBLIC_SIGNUP_REQUIRE_VERIFICATION', True) and backend in inert:
        errors.append(Warning(
            f'PUBLIC_SIGNUP_REQUIRE_VERIFICATION is on but EMAIL_BACKEND is {backend!r}, '
            'which does not deliver mail.',
            hint='Configure a real EMAIL_BACKEND in settings_lab.py, or set '
                 'PUBLIC_SIGNUP_REQUIRE_VERIFICATION = False to activate accounts immediately.',
            id='misc.W001'))
    return errors


def check_sso_settings(app_configs, **kwargs):
    """Report a single sign-on configuration that would fail, or would be unsafe, at run time.

    SSO is optional and off by default, so none of this applies to a deployment that has not
    asked for it. Where it has, the failure modes are all silent: a missing dependency only
    surfaces on the first sign-in attempt, and an over-permissive policy only surfaces as
    people being let in who should not be.
    """
    errors = []
    if not getattr(settings, 'SSO_ENABLED', False):
        return errors

    from misc import sso
    if sso.DefaultSocialAccountAdapter is None:
        errors.append(Error(
            'SSO_ENABLED is set but django-allauth is not installed.',
            hint='Install the optional dependency with `pip install alyx[sso]`, or set '
                 'SSO_ENABLED = False.',
            id='misc.E001'))
        return errors  # nothing below can be checked without it

    provider = getattr(settings, 'SSO_PROVIDER', '')
    app = (getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {}) or {}).get(provider, {}).get('APP')
    if not app or not app.get('client_id') or not app.get('secret'):
        errors.append(Error(
            f'SSO_ENABLED is set but SOCIALACCOUNT_PROVIDERS has no client_id/secret for '
            f'provider {provider!r}.',
            hint='Add them in settings_lab.py; see the single sign-on section of '
                 'docs/03_deployment.md.',
            id='misc.E002'))

    if getattr(settings, 'SSO_CREATE_USER', False) and not (
            getattr(settings, 'PUBLIC_DATABASE', False)
            or getattr(settings, 'SSO_ALLOWED_DOMAINS', ())):
        errors.append(Warning(
            'SSO_CREATE_USER is on for an internal database with no SSO_ALLOWED_DOMAINS, so '
            'anyone who can sign in at the identity provider gets an Alyx account.',
            hint='Set SSO_ALLOWED_DOMAINS to your institution, or leave SSO_CREATE_USER off so '
                 'that SSO only signs in accounts that already exist.',
            id='misc.W002'))

    if getattr(settings, 'SSO_ALLOW_SUPERUSER', False):
        errors.append(Warning(
            'SSO_ALLOW_SUPERUSER is on, so a superuser account can be signed into with '
            'credentials the identity provider controls rather than Alyx.',
            id='misc.W003'))

    if getattr(settings, 'SOCIALACCOUNT_STORE_TOKENS', False):
        errors.append(Warning(
            'SOCIALACCOUNT_STORE_TOKENS is on, so the provider access tokens issued to Alyx '
            'are kept in the database. They authenticate Alyx to the provider and are not '
            'needed to sign users in.',
            hint='Leave it off unless Alyx calls the provider API on a user\'s behalf.',
            id='misc.W004'))

    return errors
