from django.urls import path, re_path
from django.views.generic.base import RedirectView
from misc import views as mv
from django.conf.urls import include
from django.conf import settings

from misc.signup.urls import preferences_urlpatterns, public_urlpatterns

media_url = settings.MEDIA_URL.strip('/')

urlpatterns = [
    path('', RedirectView.as_view(url='/admin')),  # redirect the page to admin interface
    path('labs', mv.LabList.as_view(), name="lab-list"),
    path('labs/<str:name>', mv.LabDetail.as_view(), name="lab-detail"),
    path('notes', mv.NoteList.as_view(), name="note-list"),
    path('notes/<uuid:pk>', mv.NoteDetail.as_view(), name="note-detail"),
    path('users', mv.UserList.as_view(), name="user-list"),
    path('users/<str:username>', mv.UserDetail.as_view(), name="user-detail"),
    re_path(fr'^{media_url}/(?P<img_url>.*)', mv.UploadedView.as_view(), name='uploaded'),
    path('cache.zip', mv.CacheDownloadView.as_view(), name='cache-download'),
    re_path(r'^cache/info(?:/(?P<tag>\w+))?/$', mv.CacheVersionView.as_view(), name='cache-info'),
]

# Where a user finds their REST API token, so routed on every deployment.
urlpatterns += [path('me', mv.MeView.as_view(), name='me')]

if getattr(settings, 'EMAIL_PREFERENCES', None):
    urlpatterns += preferences_urlpatterns

# A client handed only a base URL will probe it, and `/` serves an HTML login page that tells
# a machine nothing. llms.txt is the same idea for clients that look for one.
urlpatterns += [
    path('api/', mv.api_root, name='api-root'),
    path('llms.txt', mv.LLMsTextView.as_view(), name='llms-txt'),
]

if getattr(settings, 'PUBLIC_DATABASE', False):
    urlpatterns += public_urlpatterns

if getattr(settings, 'SSO_ENABLED', False):
    # allauth provides the provider handshake, the callback, and account connection management.
    urlpatterns += [path('accounts/', include('allauth.urls'))]

try:
    # If ibl-reports redirect home to reports page
    urlpatterns += [path('ibl_reports/', include('ibl_reports.urls')), ]
    # urlpatterns += [path('', RedirectView.as_view(url='/ibl_reports/overview')), ]
except ModuleNotFoundError:
    pass
    # redirect the page to admin interface
    # urlpatterns += [path('', RedirectView.as_view(url='/admin')), ]
