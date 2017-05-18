import csv
import logging
# from datetime import datetime
import os.path as op

from django.db import models
from django.utils import timezone
from actions.models import WaterRestriction, Weighing, WaterAdministration

logger = logging.getLogger(__name__)


def today():
    return timezone.now()


def expected_weighing_mean_std(sex, age_w):
    sex = 'male' if sex == 'M' else 'female'
    path = op.join(op.dirname(__file__),
                   'static/ref_weighings_%s.csv' % sex)
    with open(path, 'r') as f:
        reader = csv.reader(f)
        d = {int(age): (float(m), float(s))
             for age, m, s in list(reader)}
    age_min, age_max = min(d), max(d)
    if age_w < age_min:
        return d[age_min]
    elif age_w > age_max:
        return d[age_max]
    else:
        return d[age_w]


def to_weeks(birth_date, dt):
    if not dt:
        return 0
    return (dt.date() - birth_date).days // 7


def last_water_restriction(subject, date=None):
    """Start of the last ongoing water restriction before specified date."""
    restriction = WaterRestriction.objects.filter(subject=subject,
                                                  end_time__isnull=True,
                                                  start_time__lte=date or today(),
                                                  )
    restriction = restriction.order_by('-start_time').first()
    if not restriction:
        return
    return restriction.start_time


def reference_weighing(subject, date=None):
    """Last weighing before the last ongoing water restriction."""
    wr_date = last_water_restriction(subject, date=date)
    if not wr_date:
        return None
    return Weighing.objects.filter(subject=subject,
                                   date_time__lte=wr_date).order_by('-date_time').first()


def current_weighing(subject, date=None):
    return (Weighing.objects.filter(subject=subject, date_time__lte=date or today()).
            order_by('-date_time').first())


def weight_zscore(subject, date=None):
    rw = reference_weighing(subject, date=date)
    if not rw:
        return 0
    iw = subject.implant_weight or 0
    # Age at the time of the reference weighing.
    age = to_weeks(subject.birth_date, rw.date_time)
    # Expected mean/std at that time.
    mrw, srw = expected_weighing_mean_std(subject.sex, age)
    # Reference weight.
    weight = rw.weight
    return (weight - iw - mrw) / srw


def expected_weighing(subject, date=None):
    rw = reference_weighing(subject)
    if not rw:
        return 0
    iw = subject.implant_weight or 0
    age = to_weeks(subject.birth_date, date or today())
    mrw, srw = expected_weighing_mean_std(subject.sex, age)
    subj_zscore = weight_zscore(subject)
    return (srw * subj_zscore) + mrw + iw


def water_requirement_total(subject, date=None):
    """Returns the amount of water the subject needs today in total"""
    if not last_water_restriction(subject, date=date):
        return 0
    if not subject.birth_date:
        logger.warn("Subject %s has no birth date!", subject)
        return 0
    # Return the amount of water the subject needs today in total.
    expected_weight = expected_weighing(subject, date=date)
    if not expected_weight:
        return 0
    iw = subject.implant_weight or 0
    weight = current_weighing(subject, date=date).weight
    return 0.05 * (weight - iw) if weight < 0.8 * expected_weight else 0.04 * (weight - iw)


def water_requirement_remaining(subject, date=None):
    """Returns the amount of water the subject still needs, given how much it got already today"""
    if not last_water_restriction(subject, date=date):
        return 0
    req_total = water_requirement_total(subject, date=date)
    water_today = WaterAdministration.objects.filter(subject=subject,
                                                     date_time__date=date or today())
    # Extract the amounts of all water_today, sum them, subtract from req_total.
    water_today = water_today.aggregate(models.Sum('water_administered'))
    return req_total - (water_today['water_administered__sum'] or 0)
