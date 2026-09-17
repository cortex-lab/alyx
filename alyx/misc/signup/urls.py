"""Routes for public self-registration and email preferences.

Both lists are conditional in misc/urls.py, and kept separate so misc.tests_urls can route them
whatever the test settings say.
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views as sv

# Self-registration and the password reset flow that makes those accounts recoverable. The
# reset views take the admin_password_reset / password_reset_done names so the admin login page
# shows its "Forgotten your password?" link and its templates are reused.
public_urlpatterns = [
    path('signup', sv.SignUpView.as_view(), name='signup'),
    path('signup/done', sv.SignUpDoneView.as_view(), name='signup-done'),
    path('signup/verify/<uidb64>/<token>', sv.SignUpVerifyView.as_view(), name='signup-verify'),
    path('password_reset/', auth_views.PasswordResetView.as_view(),
         name='admin_password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]

preferences_urlpatterns = [
    path('me/preferences', sv.PreferencesView.as_view(), name='preferences'),
    path('me/preferences/verify/<uidb64>/<token>', sv.EmailVerifyView.as_view(),
         name='email-verify'),
]
