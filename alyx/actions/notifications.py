import logging
from textwrap import dedent

from django.utils import timezone

from actions.models import create_notification


logger = logging.getLogger(__name__)


def responsible_user_changed(subject, old_user, new_user):
    """Send a notification when a responsible user changes."""
    msg = 'Responsible user of %s changed from %s to %s' % \
          (subject, old_user.username, new_user.username)
    create_notification('responsible_user_change', msg, subject, users=[old_user, new_user])


def check_underweight(subject, date=None):
    """Called when a weighing is added."""
    # Reinit the water_control instance to make sure the just-added
    # weighing is taken into account
    wc = subject.water_control
    perc = wc.percentage_weight(date=date)
    min_perc = wc.min_percentage(date=date)
    lwb = wc.last_weighing_before(date=date)
    datetime = lwb[0] if lwb else None
    if 0 < perc <= min_perc + 2:
        header = 'WARNING' if perc <= min_perc else 'ATTENTION'
        msg = "%s: %s weight was %.1f%% on %s" % (header, subject, perc, datetime)
        create_notification('mouse_underweight', msg, subject)


def check_weighed(subject, date=None):
    """Check the a subject was weighed in the last 24 hours."""
    date = date or timezone.now()
    # Reinit the water_control instance to make sure the just-added
    # weighing is taken into account
    wc = subject.water_control
    if not wc or not wc.is_water_restricted(date):
        return

    assert hasattr(date, 'date')
    ref_weight = wc.reference_weight(date)
    is_restriction_day = wc.water_restriction_at(date).date() == date.date()
    # Don't notifiy if a reference weight was entered and subject
    # was put on water restriction on the same day
    if is_restriction_day and ref_weight:
        return

    lwb = wc.last_weighing_before(date=date)
    date = date.date()

    datetime = lwb[0] if lwb else None
    if not datetime or datetime.date() != date:
        header = 'ATTENTION'
        msg = '%s: subject "%s" weighing missing for %s' % (header, wc.nickname, date)
        create_notification('mouse_not_weighed', msg, subject)


def check_water_administration(subject, date=None):
    """
    Check the subject was administered water in the last 24 hours.

    Creates a notification if the subject was not given required water
    today.

    Parameters
    ----------
    subject : subject.models.Subject
        A subject instance.
    date : datetime.datetime
        The datetime to check, deafults to now.
    """
    date = date or timezone.now()
    wc = subject.water_control
    if not wc or not wc.is_water_restricted(date):
        return
    remaining = wc.remaining_water(date=date)
    wa = wc.last_water_administration_at(date=date)
    # If the subject is not on water restriction, or the restriction
    # was created on the same day, water administration is not required
    if wc.water_restriction_at(date).date() == date.date():
        return
    delay = date - (wa[0] if wa else wc.current_water_restriction())
    # Notification if water needs to be given more than 23h after the last
    # water administration.
    if remaining > 0 and delay.total_seconds() >= 23 * 3600 - 10:
        msg = "%.1f mL remaining for %s" % (remaining, subject)
        details = dedent('''
        Mouse: %s
        User: %s
        Date: %s
        Last water administration: %s, %.2f mL
        Remaining water: %.1f mL
        Delay: %.1f hours
        ''' % (
            subject.nickname,
            subject.responsible_user.username,
            date.strftime('%Y-%m-%d %H:%M:%S'),
            wa[0].strftime('%Y-%m-%d %H:%M:%S'), wa[1],
            remaining, (delay.total_seconds() / 3600)))
        create_notification('mouse_water', msg, subject, details=details)
