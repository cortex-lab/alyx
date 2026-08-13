"""URLconf for the public sign-up tests.

misc.urls only routes the registration views when PUBLIC_DATABASE is set, which is decided when
the module is imported and so cannot be changed by override_settings. Tests point ROOT_URLCONF
here instead to route them unconditionally, then use override_settings(PUBLIC_DATABASE=...) to
exercise the check the views themselves make.
"""
from alyx.urls import urlpatterns as alyx_urlpatterns
from misc.urls import public_urlpatterns

urlpatterns = alyx_urlpatterns + public_urlpatterns
