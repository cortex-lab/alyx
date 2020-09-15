import os.path as op

import magic
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from rest_framework import viewsets, views
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework import generics, permissions

from alyx.base import BaseFilterSet
from .serializers import UserSerializer, LabSerializer
from .models import Lab
from alyx.settings import MEDIA_ROOT


@api_view(['GET'])
def api_root(request, format=None):
    """**[==========> CLICK HERE TO GO TO THE ADMIN INTERFACE <==========](/admin)**

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
        'projects-url': reverse('project-list', request=request, format=format),
        'labs-url': reverse('lab-list', request=request, format=format),
        'datasets-url': reverse('dataset-list', request=request, format=format),
        'files-url': reverse('filerecord-list', request=request, format=format),

        'datarepository-url': reverse('datarepository-list', request=request, format=format),
        'datarepositorytype-url': reverse(
            'datarepositorytype-list', request=request, format=format),

        'dataformat-url': reverse('dataformat-list', request=request, format=format),
        'dataset-types-url': reverse('datasettype-list', request=request, format=format),
        'register-file': reverse(
            'register-file', request=request, format=format),

        'weighings-url': reverse('weighing-create', request=request, format=format),

        'water-restricted-subjects-url': reverse(
            'water-restricted-subject-list', request=request, format=format),

        'water-administrations-url': reverse(
            'water-administration-create', request=request, format=format),

        #'water-requirement-url': reverse(
        #    'water-requirement', request=request, format=format),

    })


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lists all users with the subjects which they are responsible for.
    """
    queryset = get_user_model().objects.all()
    queryset = UserSerializer.setup_eager_loading(queryset)
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = (permissions.IsAuthenticated,)


class LabFilter(BaseFilterSet):
    pass

    class Meta:
        model = Lab
        exclude = ['json']


class LabList(generics.ListCreateAPIView):
    queryset = Lab.objects.all()
    serializer_class = LabSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'
    filter_class = LabFilter


class LabDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Lab.objects.all()
    serializer_class = LabSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class UploadedView(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request=None, format=None, img_url=''):
        path = op.join(MEDIA_ROOT, img_url)
        mime = magic.from_file(path, mime=True)
        with open(path, 'rb') as f:
            data = f.read()
        return HttpResponse(data, content_type=mime)
