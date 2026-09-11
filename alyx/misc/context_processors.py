from django.conf import settings
from django.urls import NoReverseMatch, reverse


def public_database(request):
    """Expose the deployment-shape settings that shared templates branch on.

    Lets the admin login page offer registration and single sign-on only where those are
    actually routed. The sign-in URL is resolved here rather than in the template, because
    allauth's provider_login_url tag lives in a template library that does not exist on a
    deployment without the optional dependency, and {% load %} cannot be made conditional.
    """
    context = {
        'PUBLIC_DATABASE': getattr(settings, 'PUBLIC_DATABASE', False),
        'SSO_ENABLED': getattr(settings, 'SSO_ENABLED', False),
        'SSO_PROVIDER_NAME': getattr(settings, 'SSO_PROVIDER_NAME', 'SSO'),
        'SSO_LOGIN_URL': '',
    }
    if context['SSO_ENABLED']:
        provider = getattr(settings, 'SSO_PROVIDER', '')
        try:
            context['SSO_LOGIN_URL'] = reverse(f'{provider}_login')
        except NoReverseMatch:  # misconfigured provider; manage.py check reports it
            context['SSO_ENABLED'] = False
    return context
