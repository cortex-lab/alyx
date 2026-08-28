from django.contrib.admin.apps import AdminConfig


class AlyxAdminConfig(AdminConfig):
    """Installs MyAdminSite as Django's default admin site.

    This is the supported hook for replacing the admin site, and it must be used rather than
    reassigning ``django.contrib.admin.site``: the ``@admin.register`` decorator resolves the
    default site at import time via ``django.contrib.admin.sites.site``, so a reassignment is
    invisible to it and any app registering that way (``django.contrib.auth``,
    ``rest_framework.authtoken``, ...) would land on a site Alyx never serves.

    ``INSTALLED_APPS`` lists this in place of ``django.contrib.admin``.
    """

    default_site = 'alyx.base.MyAdminSite'
