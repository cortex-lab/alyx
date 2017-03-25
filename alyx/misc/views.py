from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse

from .serializers import UserSerializer


@api_view(['GET'])
def api_root(request, format=None):
    """
    Welcome to Alyx's API! At the moment, there is read-only support for
    unauthenticated user lists, and authenticated read-write subject metadata
    and weighings. This should be reasonably self-documented; standard REST options
    are supported by sending an `OPTIONS /api/subjects/` for example. This is in alpha
    and endpoints are subject to change at short notice!
    """
    return Response({
        'users-url': reverse('user-list', request=request, format=format),
        'subjects-url': reverse('subject-list', request=request, format=format),
        'sessions-url': reverse('session-list', request=request, format=format),
        'datasets-url': reverse('dataset-list', request=request, format=format),
        'weighings-url': reverse('weighing-create', request=request, format=format),
        'water-administrations-url': reverse('water-administration-create',
                                             request=request, format=format),
        'exp-metadata-url': reverse('exp-metadata-list', request=request, format=format),
        'files-url': reverse('filerecord-list', request=request, format=format)
    })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists all users with the subjects which they are responsible for.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'username'
