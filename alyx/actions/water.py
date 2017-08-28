import csv
import datetime
import functools
import logging
from math import erf, sqrt
import os.path as op

from django.db import models
from django.utils import timezone
from .models import WaterRestriction, Weighing, WaterAdministration

logger = logging.getLogger(__name__)


def today():
    return timezone.now().date()


# Keep the tables in memory instead of reloading the CSV files.
@functools.lru_cache(maxsize=None)
def _get_table(sex):
    sex = 'male' if sex == 'M' else 'female'
    path = op.join(op.dirname(__file__),
                   'static/ref_weighings_%s.csv' % sex)
    with open(path, 'r') as f:
        reader = csv.reader(f)
        d = {int(age): (float(m), float(s))
             for age, m, s in list(reader)}
    return d


def expected_weighing_mean_std(sex, age_w):
    d = _get_table(sex)
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
    if isinstance(dt, datetime.datetime):
        dt = dt.date()
    return (dt - birth_date).days // 7


def last_water_restriction(subject, date=None):
    """Start of the last ongoing water restriction before specified date."""
    restriction = WaterRestriction.objects.filter(subject=subject,
                                                  start_time__date__lte=date or today(),
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
                                   date_time__date__lte=wr_date).order_by('-date_time').first()


def current_weighing(subject, date=None):
    return (Weighing.objects.filter(subject=subject, date_time__date__lte=date or today()).
            order_by('-date_time').first())


def weight_zscore(subject, date=None, rw=None):
    rw = rw or reference_weighing(subject, date=date)
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


def expected_weighing(subject, date=None, rw=None):
    if isinstance(date, datetime.datetime):
        date = date.date()
    date = date or today()
    rw = rw or reference_weighing(subject, date=date)
    if not rw:
        return 0
    iw = subject.implant_weight or 0
    age = to_weeks(subject.birth_date, date)
    mrw, srw = expected_weighing_mean_std(subject.sex, age)
    subj_zscore = weight_zscore(subject, date=date, rw=rw)
    return (srw * subj_zscore) + mrw + iw


def phy(x):
    'Cumulative distribution function for the standard normal distribution'
    return (1.0 + erf(x / sqrt(2.0))) / 2.0


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
