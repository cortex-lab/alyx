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


# The model mixin method each HTTP method dispatches to on a generic view. These are also the
# action names a router gives a viewset. GET is a list or a retrieve depending on the view.
REST_ACTIONS = ('list', 'retrieve', 'create', 'update', 'partial_update', 'destroy')
_METHOD_ACTIONS = {
    'get': ('list', 'retrieve'),
    'head': ('list', 'retrieve'),
    'post': ('create',),
    'put': ('update',),
    'patch': ('partial_update',),
    'delete': ('destroy',),
}


def table_name(view):
    """The database table of the model a REST view serves, or None for a view with no model."""
    model = getattr(getattr(view, 'queryset', None), 'model', None)
    return model._meta.db_table if model is not None else None


def action_name(request, view):
    """The REST action a request is for, e.g. 'list' or 'retrieve', or None if it has none."""
    if action := getattr(view, 'action', None):  # set on a viewset
        return action
    # Checking the view rather than the URL matters: water-type/<name> routes to a list view
    candidates = _METHOD_ACTIONS.get(request.method.lower(), ())
    return next((action for action in candidates if hasattr(view, action)), None)


class TableRateThrottle(AdaptiveScopedRateThrottle):
    """Throttle REST requests by the model table they serve and, optionally, their action.

    Rates come from settings.THROTTLE_TABLE_RATES, keyed '<table>.<action>' or '<table>', e.g.
    'actions_session.list' or 'actions_session', so a deployment can limit a table without a
    change to its views. The most specific key wins and each key counts its own requests, so
    {'actions_session': '100/minute', 'actions_session.list': '10/minute'} allows 10 lists and
    100 other session requests a minute. A rate of None exempts an action from its table's rate.
    Views whose table has no rate, and views with no model, are not throttled by this class.
    """

    def allow_request(self, request, view):
        rates = getattr(settings, 'THROTTLE_TABLE_RATES', None)
        table = table_name(view) if rates else None
        if table is None:
            return True
        action = action_name(request, view)
        scopes = (f'{table}.{action}', table) if action else (table,)
        self.scope = next((scope for scope in scopes if scope in rates), None)
        if self.scope is None:
            return True
        self.rate = rates[self.scope]
        self.num_requests, self.duration = self.parse_rate(self.rate)
        # Not super(): ScopedRateThrottle.allow_request would take the scope from the view
        return SimpleRateThrottle.allow_request(self, request, view)