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

    from misc.signup import sso
    if sso.DefaultSocialAccountAdapter is None:
        errors.append(Error(
            'SSO_ENABLED is set but django-allauth is not installed.',
            hint='Install the optional dependency with `pip install alyx[sso]`, or set '
                 'SSO_ENABLED = False.',
            id='misc.E001'))
        return errors  # nothing below can be checked without it

    provider = getattr(settings, 'SSO_PROVIDER', '')
    provider_id = getattr(settings, 'SSO_PROVIDER_ID', '')
    app = sso.configured_app(provider, provider_id)
    if not app or not app.get('client_id') or not app.get('secret'):
        errors.append(Error(
            f'SSO_ENABLED is set but SOCIALACCOUNT_PROVIDERS has no client_id/secret for '
            f'provider {provider!r}'
            + (f' with provider_id {provider_id!r}.' if provider_id else '.'),
            hint='Add them in settings_lab.py; see the single sign-on section of '
                 'docs/03_deployment.md. openid_connect uses APPS, a list, rather than APP.',
            id='misc.E002'))
    elif provider == 'openid_connect' and not (app.get('settings') or {}).get('server_url'):
        errors.append(Error(
            "The openid_connect app has no settings['server_url'], which allauth reads the "
            'provider endpoints from.',
            hint='Add it to the entry in '
                 "SOCIALACCOUNT_PROVIDERS['openid_connect']['APPS'].",
            id='misc.E004'))

    # The sign-in button is built by reversing this. openid_connect routes through the app id,
    # so without SSO_PROVIDER_ID the button silently fails to render.
    from django.urls import NoReverseMatch, reverse
    try:
        reverse(f'{provider}_login', kwargs=sso.login_url_kwargs())
    except NoReverseMatch:
        errors.append(Error(
            f'The sign-in URL for provider {provider!r} cannot be reversed'
            + (f' with SSO_PROVIDER_ID {provider_id!r}.' if provider_id
               else ', so no sign-in button is shown.'),
            hint='openid_connect routes through the app id: set SSO_PROVIDER_ID to the '
                 "provider_id of the entry in SOCIALACCOUNT_PROVIDERS['openid_connect']['APPS'].",
            id='misc.E003'))

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
