#!/usr/bin/env python
import csv
import os.path as op
import sys

sys.path.append(op.abspath(op.join(op.dirname(__file__), '../alyx')))
from alyx.core import get_sheet_doc  # noqa


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


# def add_columns(path):
#     with open(path) as csvfile:
#         reader = csv.DictReader(csvfile, delimiter='\t')
#         subjects = [Bunch(_) for _ in reader]
#     # TODO: the backup query should set the fields below.
#     for subject in subjects:
#         wrt = water_requirement_total(reference_weighing=None,
#                                       current_weighing=None,
#                                       start_weight=None,
#                                       implant_weight=None,
#                                       birth_date=None,
#                                       death_date=None,
#                                       sex=None
#                                       )


def upload_gsheets(path):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    with open(path) as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        headers = next(reader)
        subjects = list(reader)
    ws = get_sheet_doc('Alyx Backup').worksheet('Subjects')
    n_rows = len(subjects)
    n_cols = len(headers)

    # Write headers.
    last_col = alphabet[n_cols - 1]
    header_list = ws.range('A1:%s1' % last_col)
    for cell in header_list:
        cell.value = headers[cell.col - 1]
    ws.update_cells(header_list)

    # Write table.
    cell_list = ws.range('A2:%s%d' % (last_col, n_rows + 1))
    for cell in cell_list:
        row, col = cell.row - 2, cell.col - 1
        subject = subjects[row]
        cell.value = subject[col]
    ws.update_cells(cell_list)

    return n_rows


output_dir = sys.argv[1]
path = op.join(output_dir, 'subjects_subject.tsv')
n_subjects = upload_gsheets(path)
print("%d subjects uploaded to Google Sheets." % n_subjects)
