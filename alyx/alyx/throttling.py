"""Throttling classes for Alyx REST API.

For Alyx instances where a single user login is shared across multiple users, we want to throttle based on IP address rather than user ID.
This module defines custom throttling classes that can be used in the Django REST Framework settings to achieve this behavior.
"""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle, ScopedRateThrottle


def _get_throttle_mode():
    return getattr(settings, 'THROTTLE_MODE', 'user-based').lower()


class IPRateThrottle(SimpleRateThrottle):
    """Throttle all requests by client IP, regardless of authentication state."""

    def get_cache_key(self, request, view):
        if self.rate is None:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


if _get_throttle_mode() == 'anonymous':
    class BurstRateThrottle(IPRateThrottle):
        scope = 'burst'


    class SustainedRateThrottle(IPRateThrottle):
        scope = 'sustained'
else:
    class BurstRateThrottle(UserRateThrottle):
        scope = 'burst'


    class SustainedRateThrottle(UserRateThrottle):
        scope = 'sustained'


class AdaptiveScopedRateThrottle(ScopedRateThrottle):
    def get_cache_key(self, request, view):
        if getattr(settings, "THROTTLE_MODE", "user-based").lower() == "anonymous":
            return self.cache_format % {
                "scope": self.scope,
                "ident": self.get_ident(request),  # always IP
            }
        return super().get_cache_key(request, view)  # default ScopedRateThrottle behavior