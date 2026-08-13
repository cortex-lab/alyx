from django.conf import settings


def public_database(request):
    """Expose PUBLIC_DATABASE to templates.

    Lets shared templates - the admin login page in particular - offer the registration link
    only on a deployment that actually has self-registration routed.
    """
    return {'PUBLIC_DATABASE': getattr(settings, 'PUBLIC_DATABASE', False)}
