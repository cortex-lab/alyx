"""Per-user email preferences, stored in LabMember.json.

Off unless a deployment configures EMAIL_PREFERENCES; an internal lab database has no reason to
ask anyone's consent to email them. Consent is opt-in: every option defaults to False, and each
change appends the previous value to a history, in the manner of Subject.json.

LabMember.json is editable=False, so nothing writes it but the code here.
"""
from django.conf import settings
from django.utils import timezone

KEY = 'email_preferences'
HISTORY = 'history'


def options():
    """Return the configured options as {field name: checkbox label}, empty if unconfigured."""
    return dict(getattr(settings, 'EMAIL_PREFERENCES', None) or {})


def get(user):
    """Return the user's preferences, defaulting every unset option to False.

    Parameters
    ----------
    user : misc.models.LabMember
        The user to read.

    Returns
    -------
    dict
        One boolean per configured option.

    """
    stored = (user.json or {}).get(KEY) or {}
    return {name: bool(stored.get(name, False)) for name in options()}


def set(user, preferences, save=True):
    """Record the user's choices, keeping the previous value of anything that changed.

    Only configured options are read from `preferences`, so a stale or tampered form cannot
    write arbitrary keys.

    Parameters
    ----------
    user : misc.models.LabMember
        The user to update.
    preferences : dict
        Option name to bool.  A missing option is recorded as False.
    save : bool
        Whether to save the user; False leaves that to the caller.

    Returns
    -------
    dict
        The preferences as stored.

    """
    now = timezone.now().isoformat()
    current = get(user)
    chosen = {name: bool(preferences.get(name, False)) for name in options()}

    stored = dict((user.json or {}).get(KEY) or {})
    history = {k: list(v) for k, v in (stored.get(HISTORY) or {}).items()}
    for name, value in chosen.items():
        if name in stored and current[name] != value:
            history.setdefault(name, []).append(
                {'date_time': now, 'value': current[name]})

    user.json = dict(user.json or {})
    # Merged, not replaced: anything else kept under this key, email_verified above all, must
    # survive a preference being saved.
    user.json[KEY] = {**stored, **chosen, 'updated': now}
    if history:
        user.json[KEY][HISTORY] = history
    if save:
        user.save(update_fields=['json'])
    return chosen


VERIFIED = 'email_verified'


def email_verified(user):
    """Whether the address on record has been confirmed by a link sent to it."""
    return bool((user.json or {}).get(KEY, {}).get(VERIFIED))


def set_email_verified(user, verified, save=True):
    """Record whether the address on record is confirmed.

    Cleared whenever the address changes, so mail only ever goes to an address someone has
    proved they can read.
    """
    user.json = dict(user.json or {})
    user.json[KEY] = {**(user.json.get(KEY) or {}), VERIFIED: bool(verified)}
    if save:
        user.save(update_fields=['json'])


def updated(user):
    """Return when the preferences were last set, or None if they never were."""
    return ((user.json or {}).get(KEY) or {}).get('updated')


def history(user, name):
    """Return the recorded previous values of one option, oldest first."""
    stored = (user.json or {}).get(KEY) or {}
    return list((stored.get(HISTORY) or {}).get(name, []))
