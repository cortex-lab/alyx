#!/usr/bin/env python
import csv
import glob
import os.path as op
import sys

import gspread
from oauth2client.service_account import ServiceAccountCredentials


def get_gc():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    path = op.join(op.dirname(__file__), '../data', 'gdrive.json')
    credentials = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
    gc = gspread.authorize(credentials)
    return gc


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def upload_gsheets(doc, path):
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    with open(path) as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        headers = next(reader)
        items = list(reader)
    # Get the sheet.
    name = op.splitext(op.basename(path))[0]
    ws = doc.worksheet(name)
    n_rows = len(items)
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
        if 0 <= row < len(items):
            item = items[row]
            if 0 <= col < len(item):
                cell.value = item[col]
    ws.update_cells(cell_list)

    return n_rows


output_dir = sys.argv[1] if len(sys.argv) >= 2 else op.join(op.dirname(__file__), 'queries')
files = sorted(glob.glob(op.join(output_dir, '*.tsv')))
gc = get_gc()
doc = gc.open('Alyx Backup')
for path in files:
    name = op.splitext(op.basename(path))[0]
    n = upload_gsheets(doc, path)
    print("%d items uploaded to `%s` sheet of Google Sheet backup document." % (n, name))
