from pathlib import Path
import logging
import os.path as op
import json

import urllib.parse
import requests
from one.remote.aws import get_s3_virtual_host
from django.contrib.auth import get_user_model
from django.http import (
    HttpResponse, FileResponse, JsonResponse, HttpResponseRedirect, HttpResponseNotFound
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from rest_framework import views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.reverse import reverse
from rest_framework import generics

from alyx.base import BaseFilterSet, LimitedLimitOffsetPagination, rest_permission_classes
from data.models import Tag
from misc.signup import preferences
from .serializers import UserSerializer, LabSerializer, NoteSerializer
from .models import Lab, Note
from alyx.settings import TABLES_ROOT, MEDIA_ROOT

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])  # an index and a how-to, not data
def api_root(request, format=None):
    """Index of the Alyx REST API.

    **Retrieving more than a page or two of records? Use
    [ONE](https://int-brain-lab.github.io/ONE/) rather than this API directly.** ONE downloads
    cache tables and queries them locally, so a search costs no database queries at all. Paging
    through large result sets here is slow, heavily rate limited, and places load on a database
    that other people are using. ONE's own documentation puts it plainly: *avoiding the database
    whenever possible is recommended ... [it] reduces the load on the remote database*.

    Page size is capped, so `?limit=10000` returns far fewer records than asked for; a response
    that has been capped says so in its `detail` field.

    Authentication is required. Every request carries `Authorization: Token <key>`; get a key
    from [your account page](/me), or by POSTing a username and password to `/auth-token`.
    Sending that header to [/me](/me) returns the account the key belongs to.

    Full schema: [/docs](/docs/) - machine-readable at [/api/schema](/api/schema).
    Model reference: [/admin/doc/models](/admin/doc/models).
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
    """Restrict public users to their own record.

    Enumerating the user table is not something a read-only account needs, and on a public
    database with self-registration it would list the accounts of members of the public. Note
    that this hides the user *records*, not the usernames attributed to data: those are still
    returned by the session, subject and dataset endpoints, and are still what
    `sessions?users=` and `subjects?responsible_user=` filter on, so the work of an anonymised
    lab member remains queryable.
    """

    def get_queryset(self):
        queryset = super(UserQuerySetMixin, self).get_queryset()
        if self.request.user.is_public_user:
            queryset = queryset.filter(pk=self.request.user.pk)
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


# Account page
# ------------------------------------------------------------------------------------------------

@method_decorator(never_cache, name='dispatch')
class MeView(LoginRequiredMixin, TemplateView):
    """The signed-in user's own account details, and their REST API token.

    Matters most for single sign-on accounts: they have no password, so neither password reset
    nor the change form can give them one, and without this page they could never use the API.
    """
    template_name = 'me.html'
    login_url = reverse_lazy('admin:login')

    def dispatch(self, request, *args, **kwargs):
        """Accept a REST API token in place of a session, for reads.

        Lets a client ask whether a token is still good and whose it is. Without it
        LoginRequiredMixin redirects, so a rejected token looks like an unread page.

        Safe methods only: a token-authenticated POST carries no CSRF token, and a credential
        that can rotate itself is a worse footgun than one that cannot.
        """
        if request.method in ('GET', 'HEAD') and 'HTTP_AUTHORIZATION' in request.META:
            from rest_framework.authentication import TokenAuthentication
            from rest_framework.exceptions import AuthenticationFailed
            try:
                authenticated = TokenAuthentication().authenticate(request)
            except AuthenticationFailed as e:
                return JsonResponse({'detail': str(e.detail)}, status=e.status_code)
            if authenticated is not None:
                request.user, request.auth = authenticated
        return super(MeView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """Render the page, or answer in JSON where the caller authenticated with a token."""
        if getattr(request, 'auth', None) is not None:
            user = request.user
            return JsonResponse({
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            })
        return super(MeView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from rest_framework.authtoken.models import Token
        context = super(MeView, self).get_context_data(**kwargs)
        user = self.request.user
        # Tokens are otherwise created on first password login via /auth-token, which an SSO
        # account never reaches.
        token, _ = Token.objects.get_or_create(user=user)
        context['token'] = token.key
        context['identities'] = self._identities(user)
        chosen = preferences.get(user)
        context['email_preferences_configured'] = bool(preferences.options())
        context['email_preferences'] = [
            label for name, label in preferences.options().items() if chosen[name]]
        context['email_verified'] = preferences.email_verified(user)
        context['has_password'] = user.has_usable_password()
        context['base_url'] = self.request.build_absolute_uri('/').rstrip('/')
        return context

    @staticmethod
    def _identities(user):
        """Linked single sign-on identities, where SSO is enabled.

        Checks the app registry because allauth raises RuntimeError, not ImportError, when it
        is installed but not in INSTALLED_APPS.
        """
        from django.apps import apps
        if not apps.is_installed('allauth.socialaccount'):
            return []
        from allauth.socialaccount.models import SocialAccount
        return list(SocialAccount.objects.filter(user=user))

    def post(self, request, *args, **kwargs):
        """Regenerate the API token, revoking the old one immediately."""
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=request.user).delete()
        Token.objects.create(user=request.user)
        logger.info('Regenerated API token for %s', request.user.username)
        return redirect('me')


class LLMsTextView(TemplateView):
    """Serve /llms.txt, a plain-text orientation for automated clients.

    An emerging convention (llmstxt.org) for handing a language model a curated entry point
    instead of leaving it to infer one from HTML. Cheap to provide and read early by clients
    that look for it, which is exactly the moment to say "use ONE, do not page this API".
    It is not a substitute for the in-band signals on capped and throttled responses: the
    clients that cause trouble are generally the ones that never fetch a file like this.
    """
    template_name = 'llms.txt'
    content_type = 'text/plain; charset=utf-8'

    def get_context_data(self, **kwargs):
        context = super(LLMsTextView, self).get_context_data(**kwargs)
        context['base_url'] = self.request.build_absolute_uri('/').rstrip('/')
        context['max_limit'] = LimitedLimitOffsetPagination.max_limit
        return context
