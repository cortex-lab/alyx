"""Views for public self-registration and email preferences.

Only routed on a deployment with PUBLIC_DATABASE set (see misc/urls.py); each view checks the
setting too, so a mistake in the URL configuration cannot expose registration on an internal
database.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView

from . import antibot, preferences
from .forms import (EmailPreferencesForm, PublicSignUpForm,
                    email_change_token_generator, signup_token_generator)

logger = logging.getLogger(__name__)


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
        if request.method == 'POST' and antibot.throttle_exceeded(request):
            # Deliberately not a form error: the throttle is about volume from one address,
            # not about anything the person filled in.
            return render(request, 'signup_throttled.html', status=429)
        return super(SignUpView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(SignUpView, self).get_form_kwargs()
        kwargs['request'] = self.request  # the form needs it to verify a Turnstile response
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(SignUpView, self).get_context_data(**kwargs)
        context['honeypot_field'] = antibot.HONEYPOT_FIELD
        context['turnstile_site_key'] = (
            settings.TURNSTILE_SITE_KEY if antibot.turnstile_configured() else '')
        return context

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
        try:
            send_mail(
                subject=render_to_string('registration/signup_subject.txt', context).strip(),
                message=render_to_string('registration/signup_email.txt', context),
                from_email=None,  # falls back to DEFAULT_FROM_EMAIL
                recipient_list=[user.email])
        except Exception:
            # The account cannot be activated without this mail, and leaving it behind would
            # hold its username and address against a retry, so it goes. Causes seen in
            # practice: a mistyped domain, and an SES account still in the sandbox, which
            # refuses any recipient that is not a verified identity.
            logger.exception('Could not send the confirmation to %s; removing the account',
                             user.email)
            user.delete()
            form.add_error(None, 'We could not send a confirmation email to that address. '
                                 'Please check it and try again.')
            return self.form_invalid(form)
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
        if not user.is_public_user or user.is_superuser:
            return False
        if not signup_token_generator.check_token(user, token):
            return False
        if not user.is_active:
            user.is_active = True
            preferences.set_email_verified(user, True, save=False)
            user.save(update_fields=['is_active', 'json'])
            logger.info('Activated public account %s', user.username)
        return True


@method_decorator(never_cache, name='dispatch')
class PreferencesView(LoginRequiredMixin, FormView):
    """Email address and mailing preferences.

    Single sign-on lands new accounts here: a provider such as ORCiD supplies no email address,
    so this is the first chance to offer one.
    """

    template_name = 'preferences.html'
    form_class = EmailPreferencesForm
    login_url = reverse_lazy('admin:login')
    success_url = reverse_lazy('me')

    def get_form_kwargs(self):
        kwargs = super(PreferencesView, self).get_form_kwargs()
        kwargs['instance'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(PreferencesView, self).get_context_data(**kwargs)
        context['first_visit'] = preferences.updated(self.request.user) is None
        context['email_verified'] = preferences.email_verified(self.request.user)
        return context

    def form_valid(self, form):
        changed = 'email' in form.changed_data
        user = form.save()
        if changed:
            preferences.set_email_verified(user, False, save=False)
            user.save(update_fields=['json'])
        # Saving again while unconfirmed sends another link, which is what the page offers as
        # the way to get one.
        if user.email and not preferences.email_verified(user):
            if not self._send_confirmation(user):
                form.add_error('email', 'We could not send a confirmation to that address. '
                                        'Please check it and try again.')
                return self.form_invalid(form)
        logger.info('Updated email preferences for %s', user.username)
        return super(PreferencesView, self).form_valid(form)

    def _send_confirmation(self, user):
        """Send the confirmation link, returning whether it went.

        Nothing is mailed to the address until it is confirmed, so a failure here leaves the
        account usable - unlike sign-up, where the mail is what activates it.
        """
        context = {
            'user': user,
            'site_name': self.request.get_host(),
            'confirmation_url': self.request.build_absolute_uri(
                reverse_lazy('email-verify', kwargs={
                    'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': email_change_token_generator.make_token(user)})),
        }
        try:
            send_mail(
                subject=render_to_string(
                    'registration/email_change_subject.txt', context).strip(),
                message=render_to_string('registration/email_change_email.txt', context),
                from_email=None,
                recipient_list=[user.email])
        except Exception:
            logger.exception('Could not send an address confirmation to %s', user.email)
            return False
        logger.info('Address confirmation sent to %s for %s', user.email, user.username)
        return True


@method_decorator(never_cache, name='dispatch')
class EmailVerifyView(LoginRequiredMixin, TemplateView):
    """Confirm a changed email address from the link sent to it."""

    template_name = 'email_verified.html'
    login_url = reverse_lazy('admin:login')

    def get_context_data(self, uidb64=None, token=None, **kwargs):
        context = super(EmailVerifyView, self).get_context_data(**kwargs)
        context['verified'] = self._verify(uidb64, token)
        return context

    def _verify(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = get_user_model().objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, ValidationError,
                get_user_model().DoesNotExist):
            return False
        # Only the signed-in user may confirm their own address; the token alone should not be
        # enough to alter another account.
        if user != self.request.user:
            return False
        if not email_change_token_generator.check_token(user, token):
            return False
        if not preferences.email_verified(user):
            preferences.set_email_verified(user, True)
            logger.info('Confirmed email address for %s', user.username)
        return True
