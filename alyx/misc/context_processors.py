import json
import os
import re

from django.conf import settings
from django.contrib import admin
from django.urls import NoReverseMatch, reverse

_CSS_VAR = re.compile(r'^--[\w-]+$')
_CSS_VALUE = re.compile(r'^[\w#%(),.\s-]+$')


def admin_theme():
    """Return the admin CSS variable overrides configured for this deployment.

    Read from the ``ADMIN_THEME`` setting (e.g. in ``settings_lab.py``), then updated with the
    ``ADMIN_THEME`` environment variable if set (a JSON object, for per-host overrides in ``.env``).
    Keys are Django admin CSS custom properties such as ``--secondary`` or ``--breadcrumbs-bg``.
    Entries that are not valid CSS variable names or plain color values are dropped.

    Returns
    -------
    dict of str to str
        Validated CSS variable names and values, empty if the admin is not customized.
    """
    theme = dict(getattr(settings, 'ADMIN_THEME', None) or {})
    if env_theme := os.getenv('ADMIN_THEME'):
        theme.update(json.loads(env_theme))
    return {k: v for k, v in theme.items()
            if _CSS_VAR.match(str(k)) and _CSS_VALUE.match(str(v))}


def public_database(request):
    """Expose the deployment-shape settings that shared templates branch on.

    Lets the admin login page offer registration and single sign-on only where those are
    actually routed. The sign-in URL is resolved here rather than in the template, because
    allauth's provider_login_url tag lives in a template library that does not exist on a
    deployment without the optional dependency, and {% load %} cannot be made conditional.
    """
    from alyx.base import is_lab_member
    user = getattr(request, 'user', None)
    context = {
        # The registration, account and single sign-on pages are styled with the admin's
        # templates but are not admin views, so admin.site.each_context() never runs for them
        # and site_header is absent - leaving them titled "Django administration". Supplying it
        # here brands them all consistently. Real admin views pass their own via each_context,
        # which takes precedence over a context processor.
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
        'ADMIN_THEME': admin_theme(),
        'PUBLIC_DATABASE': getattr(settings, 'PUBLIC_DATABASE', False),
        'SSO_ENABLED': getattr(settings, 'SSO_ENABLED', False),
        'SSO_PROVIDER_NAME': getattr(settings, 'SSO_PROVIDER_NAME', 'SSO'),
        'SSO_LOGIN_URL': '',
        # Lets shared templates hide links to pages a public account would only get a 403 from.
        'IS_LAB_MEMBER': bool(user and is_lab_member(user)),
    }
    if context['SSO_ENABLED']:
        from misc.signup.sso import login_url_kwargs
        provider = getattr(settings, 'SSO_PROVIDER', '')
        try:
            context['SSO_LOGIN_URL'] = reverse(f'{provider}_login', kwargs=login_url_kwargs())
        except NoReverseMatch:  # misconfigured provider; manage.py check reports it
            context['SSO_ENABLED'] = False
    return context
