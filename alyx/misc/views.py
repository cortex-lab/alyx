from pathlib import Path
import logging
import os.path as op
import json

import urllib.parse
import requests
from one.remote.aws import get_s3_virtual_host
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Q
from django.http import (
    HttpResponse, FileResponse, JsonResponse, HttpResponseRedirect, HttpResponseNotFound, Http404
)
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.generic import FormView, TemplateView

from rest_framework import views
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework import generics

from alyx.base import BaseFilterSet, rest_permission_classes
from data.models import Tag
from .forms import PublicSignUpForm, signup_token_generator
from .serializers import UserSerializer, LabSerializer, NoteSerializer
from .models import Lab, Note
from alyx.settings import TABLES_ROOT, MEDIA_ROOT

logger = logging.getLogger(__name__)


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


class UserFilter(BaseFilterSet):
    class Meta:
        model = get_user_model()
        exclude = ['json']


class UserQuerySetMixin:
    """Hide real accounts from public users.

    A public user may see redacted users - whose identifying details have been stripped, and
    which must stay visible so that the subjects and sessions attributed to them can still be
    looked up - plus their own record. Everything else is another person's account, and on a
    public database with self-registration that set includes members of the public.
    """

    def get_queryset(self):
        queryset = super(UserQuerySetMixin, self).get_queryset()
        if self.request.user.is_public_user:
            queryset = queryset.filter(Q(is_redacted=True) | Q(pk=self.request.user.pk))
        return queryset


class UserList(UserQuerySetMixin, generics.ListCreateAPIView):
    """
    get: **FILTERS**
    - 'id'
    - 'username'
    - 'email'
    - 'subjects_responsible'
    - 'lab'
    - 'allowed_users'
    [===> user model reference](/admin/doc/models/misc.labmember)
    """
    queryset = UserSerializer.setup_eager_loading(get_user_model().objects.all())
    serializer_class = UserSerializer
    permission_classes = rest_permission_classes()
    filterset_class = UserFilter
    lookup_field = 'username'


class UserDetail(UserQuerySetMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = UserSerializer.setup_eager_loading(get_user_model().objects.all())
    serializer_class = UserSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'username'


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
    filterset_class = LabFilter


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
    filterset_class = BaseFilterSet


class NoteDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = rest_permission_classes()


class UploadedView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, format=None, img_url=''):
        path = op.join(MEDIA_ROOT, img_url)
        return HttpResponse(path)


def _get_cache_info(tag=None):
    """
    Load and return the cache info JSON file. Contains information such as cache table timestamp,
    size and API version.

    Assumes the following folder structure:
    <TABLES_ROOT>/
    ├─ cache_info.json
    ├─ cache.zip
    ├─ <DATASET_TAG_1>/
    │  ├─ cache_info.json
    │  ├─ cache.zip

    :param: optional tag name for fetching a specific cache
    :return: dict of cache table information
    """
    META_NAME = 'cache_info.json'
    parsed = urllib.parse.urlparse(TABLES_ROOT)

    if tag:  # Validate
        Tag.objects.get(name=tag)

    scheme = parsed.scheme or 'file'  # NB: 'file' only supported on POSIX filesystems
    if scheme == 'file':
        # Cache table is local
        file_json_cache = Path(TABLES_ROOT).joinpath(tag or '', META_NAME)
        with open(file_json_cache) as fid:
            cache_info = json.load(fid)
    elif scheme.startswith('http'):
        cache_root = TABLES_ROOT.strip('/') + (f'/{tag}' if tag else '')
        file_json_cache = f'{cache_root}/{META_NAME}'
        resp = requests.get(file_json_cache)
        resp.raise_for_status()
        cache_info = resp.json()
        if 'location' not in cache_info:
            cache_info['location'] = cache_root + '/cache.zip'
    elif scheme == 's3':
        # Use PyArrow to read file from s3
        from misc.management.commands.one_cache import _s3_filesystem
        s3 = _s3_filesystem()
        cache_root = parsed.netloc + '/' + parsed.path.strip('/') + (f'/{tag}' if tag else '')
        file_json_cache = f'{cache_root}/{META_NAME}'
        with s3.open_input_stream(file_json_cache) as stream:
            cache_info = json.load(stream)
        if 'location' not in cache_info:
            cache_info['location'] = \
                get_s3_virtual_host(f'{cache_root}/cache.zip', region=s3.region)
    else:
        raise ValueError(f'Unsupported URI scheme "{scheme}"')

    return cache_info


class CacheVersionView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, tag=None, **kwargs):
        try:
            return JsonResponse(_get_cache_info(tag))
        except Tag.DoesNotExist as ex:
            return HttpResponseNotFound(str(ex))


class CacheDownloadView(views.APIView):
    permission_classes = rest_permission_classes()

    def get(self, request=None, **kwargs):
        if TABLES_ROOT.startswith('http'):
            response = HttpResponseRedirect(TABLES_ROOT.strip('/') + '/cache.zip')
        else:
            cache_file = Path(TABLES_ROOT).joinpath('cache.zip')
            response = FileResponse(open(cache_file, 'br'))
        return response


# Public self-registration
# ------------------------------------------------------------------------------------------------
# These views are only routed on a deployment with PUBLIC_DATABASE set (see misc/urls.py). They
# each check the setting as well, so that a mistake in the URL configuration of an internal
# database cannot expose a way to create accounts.

class PublicDatabaseOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, 'PUBLIC_DATABASE', False):
            raise Http404('This Alyx instance does not offer public registration.')
        return super(PublicDatabaseOnlyMixin, self).dispatch(request, *args, **kwargs)


class SignUpView(PublicDatabaseOnlyMixin, FormView):
    """Create a read-only account on a public database."""
    template_name = 'signup.html'
    form_class = PublicSignUpForm
    success_url = reverse_lazy('signup-done')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('/admin')
        return super(SignUpView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        if user.is_active:  # verification disabled, nothing to send
            logger.info('Created public account %s (no verification required)', user.username)
            return super(SignUpView, self).form_valid(form)
        context = {
            'user': user,
            'site_name': self.request.get_host(),
            'confirmation_url': self.request.build_absolute_uri(
                reverse_lazy('signup-verify', kwargs={
                    'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': signup_token_generator.make_token(user)})),
        }
        # A failure here would leave an account nobody can activate, so let it 500 rather than
        # reporting success: the address is far more likely to be mistyped than the mail server
        # broken, and the user needs to know to try again.
        send_mail(
            subject=render_to_string('registration/signup_subject.txt', context).strip(),
            message=render_to_string('registration/signup_email.txt', context),
            from_email=None,  # falls back to DEFAULT_FROM_EMAIL
            recipient_list=[user.email])
        logger.info('Created public account %s, confirmation sent', user.username)
        return super(SignUpView, self).form_valid(form)


class SignUpDoneView(PublicDatabaseOnlyMixin, TemplateView):
    template_name = 'signup_done.html'

    def get_context_data(self, **kwargs):
        context = super(SignUpDoneView, self).get_context_data(**kwargs)
        context['verification_required'] = getattr(
            settings, 'PUBLIC_SIGNUP_REQUIRE_VERIFICATION', True)
        return context


class SignUpVerifyView(PublicDatabaseOnlyMixin, TemplateView):
    """Activate an account from the link sent to its email address."""
    template_name = 'signup_verified.html'

    def get_context_data(self, uidb64=None, token=None, **kwargs):
        context = super(SignUpVerifyView, self).get_context_data(**kwargs)
        context['verified'] = self._verify(uidb64, token)
        return context

    def _verify(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_user_model().objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, ValidationError,
                get_user_model().DoesNotExist):
            return False
        # Only ever activates a self-registered public account: the token would not validate for
        # anyone else, but an activation path that could reach a staff account is worth closing
        # off explicitly rather than relying on that.
        if not user.is_public_user or user.is_redacted or user.is_superuser:
            return False
        if not signup_token_generator.check_token(user, token):
            return False
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            logger.info('Activated public account %s', user.username)
        return True
