"""Forms for public self-registration.

Only used on a deployment with PUBLIC_DATABASE set; see misc.views.SignUpView.
"""
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from . import antibot, preferences
from misc.models import LabMember

# Group granting read-only access to a public database. Created by the set_public_permissions
# management command, which is also what decides the permissions it carries.
PUBLIC_GROUP_NAME = 'Public users'

logger = logging.getLogger(__name__)


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    """Generates the token in the link confirming a changed email address.

    The hash covers the address itself, so a link dies as soon as the address changes again and
    cannot confirm an address the user has since moved away from. It deliberately does not cover
    is_active or last_login: unlike the sign-up link this confirms an account already in use.
    """

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{timestamp}'


class SignupTokenGenerator(PasswordResetTokenGenerator):
    """Generates the token in a registration confirmation link.

    Built on the password reset generator so that the link expires after
    settings.PASSWORD_RESET_TIMEOUT.

    The hash covers the account state a confirmation link should not outlive: changing the
    password or the email address invalidates it, and so does the first login. That last one is
    what stops a link being replayed to undo an administrator disabling an account - once the
    account has been used, the link is permanently dead. Hashing is_active alone would not
    achieve this, because disabling the account restores the original hash inputs and so
    revalidates the original link.
    """

    def _make_hash_value(self, user, timestamp):
        login = '' if user.last_login is None else user.last_login.replace(microsecond=0,
                                                                           tzinfo=None)
        return f'{user.pk}{user.password}{user.email}{user.is_active}{login}{timestamp}'


signup_token_generator = SignupTokenGenerator()
email_change_token_generator = EmailChangeTokenGenerator()


class PublicSignUpForm(UserCreationForm):
    """Registration form for a member of the public requesting read-only access."""

    email = forms.EmailField(
        required=True,
        help_text='Required. Used to confirm your account and to reset a forgotten password.')

    class Meta:
        model = LabMember
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(PublicSignUpForm, self).__init__(*args, **kwargs)
        # Django's admin-facing user creation form offers the option of creating an account
        # with an unusable password. That is never appropriate for self-registration.
        self.fields.pop('usable_password', None)
        # Hidden from people by the template, so anything that fills it in is a form-filling
        # bot. Not required, and never shown as an error - a bot learns nothing from a
        # rejection that names the field that caught it.
        self.fields[antibot.HONEYPOT_FIELD] = forms.CharField(
            required=False, label='', widget=forms.TextInput(attrs={
                'autocomplete': 'off', 'tabindex': '-1', 'aria-hidden': 'true'}))
        if antibot.turnstile_configured():
            self.fields['cf-turnstile-response'] = forms.CharField(
                required=False, widget=forms.HiddenInput())
        for label, description in preferences.options().items():
            self.fields[label] = forms.BooleanField(
                required=False, initial=False, label=label, help_text=description)

    def clean(self):
        cleaned = super(PublicSignUpForm, self).clean()
        if antibot.honeypot_tripped(self.data):
            logger.warning('Sign-up rejected: honeypot field completed')
            raise forms.ValidationError(
                'Your submission could not be processed. Please try again.')
        if antibot.turnstile_configured() and not antibot.turnstile_passed(
                self.request, self.data.get('cf-turnstile-response')):
            raise forms.ValidationError(
                'Could not confirm you are human. Please try again.')
        return cleaned

    def clean_username(self):
        username = self.cleaned_data['username']
        reserved = {name.lower() for name in
                    getattr(settings, 'PUBLIC_SIGNUP_RESERVED_USERNAMES', ())}
        if username.lower() in reserved:
            raise forms.ValidationError('This username is reserved, please choose another.')
        return username

    def clean_email(self):
        # AbstractUser.email is not unique, so this is enforced here rather than by the model.
        email = self.cleaned_data['email']
        if LabMember.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account already exists for this email address. Use the password reset page '
                'if you have forgotten your password.')
        return email

    def save(self, commit=True):
        user = super(PublicSignUpForm, self).save(commit=False)
        user.is_public_user = True  # read-only, enforced by alyx.base
        user.is_superuser = False
        user.is_stock_manager = False
        # Staff status is what lets a user reach the admin site at all. Public users get it so
        # they can browse released data there; the Public users group grants only view access.
        user.is_staff = True
        user.is_active = not getattr(settings, 'PUBLIC_SIGNUP_REQUIRE_VERIFICATION', True)
        preferences.set(user, self.cleaned_data, save=False)
        if commit:
            user.save()
            group, _ = Group.objects.get_or_create(name=PUBLIC_GROUP_NAME)
            user.groups.add(group)
        return user


class EmailPreferencesForm(forms.ModelForm):
    """Email address and mailing preferences, for the /me/preferences page.

    The address is optional: an account that signed in through a provider supplying none can
    stay without one, and only needs it to receive mail it has asked for.
    """

    email = forms.EmailField(
        required=False,
        help_text='Optional. Only used for the mail you choose below, and to reset a password.')

    class Meta:
        model = LabMember
        fields = ('email',)

    def __init__(self, *args, **kwargs):
        super(EmailPreferencesForm, self).__init__(*args, **kwargs)
        current = preferences.get(self.instance)
        for label, description in preferences.options().items():
            self.fields[label] = forms.BooleanField(
                required=False, initial=current[label], label=label, help_text=description)

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and LabMember.objects.filter(
                email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email address.')
        return email

    def clean(self):
        cleaned = super(EmailPreferencesForm, self).clean()
        if any(cleaned.get(name) for name in preferences.options()) and not cleaned.get('email'):
            raise forms.ValidationError(
                'Enter an email address to receive the mail you have selected.')
        return cleaned

    def save(self, commit=True):
        user = super(EmailPreferencesForm, self).save(commit=False)
        preferences.set(user, self.cleaned_data, save=False)
        if commit:
            user.save()
        return user
