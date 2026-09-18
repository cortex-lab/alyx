"""REST permission classes that settings refer to by name.

DEFAULT_PERMISSION_CLASSES is resolved from inside rest_framework.views while that module is
still part way through importing, so anything named there must not reach back into it. Keep
this module free of Alyx imports and of rest_framework.views (alyx.views pulls it in through
drf_spectacular, which is why this does not live there).
"""
from rest_framework.permissions import BasePermission


class BaseRestPermission(BasePermission):
    """Same policy as alyx.base.rest_permission_classes, as a single named class.

    Applied as DEFAULT_PERMISSION_CLASSES so a view that forgets to set permission_classes is
    not served to anonymous clients, which is what DRF's own AllowAny default would do.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method == 'GET' or not request.user.is_public_user
