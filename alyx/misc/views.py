from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics, permissions, renderers, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, detail_route
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
        'users': reverse('user-list', request=request, format=format),
        'subjects': reverse('subject-list', request=request, format=format),
        'experiments': reverse('action-list', request=request, format=format),
        'datasets': reverse('dataset-list', request=request, format=format),
        'weights': reverse('weights-list', request=request, format=format, kwargs={'nickname': 'NICKNAME'}),
        'water': reverse('water-list', request=request, format=format, kwargs={'nickname': 'NICKNAME'})
    })

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists all users with the subjects which they are responsible for.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field='username'