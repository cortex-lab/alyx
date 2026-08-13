from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Warning, register


class UsersConfig(AppConfig):
    name = 'misc'

    def ready(self):
        register(check_public_signup_settings)


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
