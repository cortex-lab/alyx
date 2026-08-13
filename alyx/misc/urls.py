from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.views.generic.base import RedirectView
from misc import views as mv
from django.conf.urls import include
from alyx.settings import MEDIA_URL, PUBLIC_DATABASE

media_url = MEDIA_URL.strip('/')

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

# Self-registration, plus the password reset flow that makes self-registered accounts
# recoverable without an administrator. The reset views are named admin_password_reset /
# password_reset_done etc. because that is what django.contrib.admin looks for when deciding
# whether to show the "Forgotten your password?" link on its login page; naming them so reuses
# the templates the admin already ships.
# Only routed on a public database (the views check the setting too). Kept as a separate list
# so that misc.tests_urls can route them regardless of how the test settings are configured.
public_urlpatterns = [
    path('signup', mv.SignUpView.as_view(), name='signup'),
    path('signup/done', mv.SignUpDoneView.as_view(), name='signup-done'),
    path('signup/verify/<uidb64>/<token>', mv.SignUpVerifyView.as_view(), name='signup-verify'),
    path('password_reset/', auth_views.PasswordResetView.as_view(),
         name='admin_password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]

if PUBLIC_DATABASE:
    urlpatterns += public_urlpatterns

try:
    # If ibl-reports redirect home to reports page
    urlpatterns += [path('ibl_reports/', include('ibl_reports.urls')), ]
    # urlpatterns += [path('', RedirectView.as_view(url='/ibl_reports/overview')), ]
except ModuleNotFoundError:
    pass
    # redirect the page to admin interface
    # urlpatterns += [path('', RedirectView.as_view(url='/admin')), ]
