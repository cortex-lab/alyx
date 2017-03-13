
import csv
from datetime import datetime
import logging
import os.path as op
from django.utils import timezone

import gspread
from oauth2client.service_account import ServiceAccountCredentials

DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


logger = logging.getLogger(__name__)


def get_sheet_doc(doc_name):
    scope = ['https://spreadsheets.google.com/feeds']
    path = op.join(DATA_DIR, 'gdrive.json')
    credentials = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
    gc = gspread.authorize(credentials)
    return gc.open(doc_name)


def get_table(doc_name, sheet_name, header_line=0, first_line=2):
    return sheet_to_table(get_sheet_doc(doc_name).worksheet(sheet_name),
                          header_line=header_line,
                          first_line=first_line,
                          )


def sheet_to_table(wks, header_line=2, first_line=3):
    rows = wks.get_all_values()
    table = []
    headers = rows[header_line]
    for row in rows[first_line:]:
        l = {headers[i].strip(): row[i].strip() for i in range(len(headers))}
        # Empty line = end of table.
        if all(_ == '' for _ in l.values()):
            break
        table.append(l)
    return table


def get_age_days(birth_date=None, death_date=None):
    return (death_date or datetime.now(timezone.utc).date() - birth_date).days


def expected_weighing_mean_std(sex, age_w):
    sex = 'male' if sex == 'M' else 'female'
    path = op.join(op.dirname(__file__), 'static/ref_weighings_%s.csv' % sex)
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


def water_requirement_total(reference_weighing=None,
                            current_weighing=None,
                            start_weight=None,
                            implant_weight=None,
                            birth_date=None,
                            death_date=None,
                            sex=None,
                            ):
    # returns the amount of water the subject needs today in total

    rw = reference_weighing
    cw = current_weighing
    implant_weight = implant_weight or 0
    age_days = get_age_days(birth_date=birth_date, death_date=death_date)

    if not birth_date:
        logger.warn("Subject has no birth date!")
        return 0
    start_age = (rw.date_time.date() - birth_date).days // 7

    today_weight = cw.weight
    today_age = age_days // 7  # in weeks

    start_mrw, start_srw = expected_weighing_mean_std(sex, start_age)
    today_mrw, today_srw = expected_weighing_mean_std(sex, today_age)

    subj_zscore = (start_weight - implant_weight - start_mrw) / start_srw

    expected_weight_today = (today_srw * subj_zscore) + \
        today_mrw + implant_weight
    thresh_weight = 0.8 * expected_weight_today

    if today_weight < thresh_weight:
        return 0.05 * today_weight
    else:
        return 0.04 * today_weight
