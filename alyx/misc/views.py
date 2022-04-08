from pathlib import Path
import os.path as op
import json
import urllib.parse

import magic
import requests
from django.contrib.auth import get_user_model
from django.http import HttpResponse, FileResponse, JsonResponse, HttpResponseRedirect

from rest_framework import viewsets, views
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework import generics

from alyx.base import BaseFilterSet, rest_permission_classes
from .serializers import UserSerializer, LabSerializer, NoteSerializer
from .models import Lab, Note
from alyx.settings import TABLES_ROOT, MEDIA_ROOT


@api_view(['GET'])
def api_root(request, format=None):
    """**[==========> CLICK HERE TO GO TO THE ADMIN INTERFACE <==========](/admin)**

    Welcome to Alyx's API! At the moment, there is read-only support for
    unauthenticated user lists, and authenticated read-write subject metadata
    and weighings. This should be reasonably self-documented; standard REST options
    are supported by sending an `OPTIONS /api/subjects/` for example. This is in alpha
    and endpoints are subject to change at short notice!

    **[ ===> Models documentation](/admin/doc/models)**

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
    permission_classes = rest_permission_classes()


class LabFilter(BaseFilterSet):
    pass

    class Meta:
        model = Lab
        exclude = ['json']


class LabList(generics.ListCreateAPIView):
    queryset = Lab.objects.all()
    serializer_class = LabSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'
    filter_class = LabFilter


class LabDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Lab.objects.all()
    serializer_class = LabSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class NoteList(generics.ListCreateAPIView):
    """
    post:
    If an image is provided, the request body can contain an additional item

    `width`: desired width to resize the image for storage. Aspect ratio will be maintained.
    Options are

    - **None** to use the UPLOADED_IMAGE_WIDTH specified in settings (default)
    - **'orig'** to keep original image size
    - any **integer** to specify the image width
    """
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = rest_permission_classes()
    filter_class = BaseFilterSet


class NoteDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = rest_permission_classes()


class UploadedView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, format=None, img_url=''):
        path = op.join(MEDIA_ROOT, img_url)
        mime = magic.from_file(path, mime=True)
        with open(path, 'rb') as f:
            data = f.read()
        return HttpResponse(data, content_type=mime)


def _get_cache_info():
    """
    Load and return the cache info JSON file. Contains information such as cache table timestamp,
    size and API version.

    :return: dict of cache table information
    """
    META_NAME = 'cache_info.json'
    parsed = urllib.parse.urlparse(TABLES_ROOT)
    scheme = parsed.scheme or 'file'
    if scheme == 'file':
        # Cache table is local
        file_json_cache = Path(TABLES_ROOT).joinpath(META_NAME)
        with open(file_json_cache) as fid:
            cache_info = json.load(fid)
    elif scheme.startswith('http'):
        file_json_cache = TABLES_ROOT.strip('/') + f'/{META_NAME}'
        resp = requests.get(file_json_cache)
        resp.raise_for_status()
        cache_info = resp.json()
        if 'location' not in cache_info:
            cache_info['location'] = TABLES_ROOT.strip('/') + '/cache.zip'
    elif scheme == 's3':
        # Use PyArrow to read file from s3
        from misc.management.commands.one_cache import _s3_filesystem
        s3 = _s3_filesystem()
        file_json_cache = parsed.netloc + '/' + parsed.path.strip('/') + '/' + META_NAME
        with s3.open_input_stream(file_json_cache) as stream:
            cache_info = json.load(stream)
        if 'location' not in cache_info:
            cache_info['location'] = TABLES_ROOT.strip('/') + '/' + META_NAME
    else:
        raise ValueError(f'Unsupported URI scheme "{scheme}"')

    return cache_info


class CacheVersionView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, **kwargs):
        return JsonResponse(_get_cache_info())


class CacheDownloadView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, **kwargs):
        if TABLES_ROOT.startswith('http'):
            response = HttpResponseRedirect(TABLES_ROOT.strip('/') + '/cache.zip')
        else:
            cache_file = Path(TABLES_ROOT).joinpath('cache.zip')
            response = FileResponse(open(cache_file, 'br'))
        return response
