"""Forms for public self-registration.

Only used on a deployment with PUBLIC_DATABASE set; see misc.views.SignUpView.
"""
from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from misc.models import LabMember

# Group granting read-only access to a public database. Created by the set_public_permissions
# management command, which is also what decides the permissions it carries.
PUBLIC_GROUP_NAME = 'Public users'


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


class PublicSignUpForm(UserCreationForm):
    """Registration form for a member of the public requesting read-only access."""

    email = forms.EmailField(
        required=True,
        help_text='Required. Used to confirm your account and to reset a forgotten password.')

    class Meta:
        model = LabMember
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super(PublicSignUpForm, self).__init__(*args, **kwargs)
        # Django's admin-facing user creation form offers the option of creating an account
        # with an unusable password. That is never appropriate for self-registration.
        self.fields.pop('usable_password', None)

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
        if commit:
            user.save()
            group, _ = Group.objects.get_or_create(name=PUBLIC_GROUP_NAME)
            user.groups.add(group)
        return user
