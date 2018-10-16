import csv
from datetime import datetime
import glob
import logging
import math
import os
import os.path as op
import sys

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


def get_gc():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    path = op.join(op.dirname(__file__), '../../../../data', 'gdrive.json')
    credentials = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
    gc = gspread.authorize(credentials)
    return gc


def backup_tsv(sql_dir, output_dir):
    path = op.abspath(op.join(sql_dir, '*.sql'))
    files = sorted(glob.glob(path))
    for file in files:
        with open(file, 'r') as f:
            sql = f.read()
        name = op.splitext(op.basename(file))[0]
        path = op.abspath(op.join(output_dir, name + '.tsv'))
        cmd = ("copy (%s) to STDOUT with CSV DELIMITER E'\t' header encoding 'utf-8'" %
               sql)
        with connection.cursor() as cursor:
            with open(path, 'w') as f:
                cursor.copy_expert(cmd, f)
        with open(path, 'r') as f:
            size = len(f.read())
        logger.info("Dumped %s to %s (%d bytes).", name, path, size)
    print("TSV backup done!")


def upload_table(doc, path):
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
    page_length = 100
    n_pages = int(math.ceil(n_rows / page_length))
    for page in range(n_pages):
        first_row = 2 + page_length * page
        last_row = min(n_rows + 1, first_row + page_length)
        assert first_row <= last_row
        cell_list = ws.range('A%d:%s%d' % (first_row, last_col, last_row))
        for cell in cell_list:
            row, col = cell.row - 2, cell.col - 1
            if 0 <= row < len(items):
                item = items[row]
                if 0 <= col < len(item):
                    cell.value = item[col]
        ws.update_cells(cell_list)

    return n_rows


def upload_gsheets(output_dir):
    gc = get_gc()
    files = sorted(glob.glob(op.join(output_dir, output_dir, '*.tsv')))
    logger.info("Found %d files in %s.", len(files), output_dir)
    doc = gc.open('Alyx Backup')
    for path in files:
        name = op.splitext(op.basename(path))[0]
        n = upload_table(doc, path)
        logger.info("%d items uploaded to `%s` sheet of Google Sheet backup document.",
                    n, name)
    print("Google upload done!")


class Command(BaseCommand):
    help = "Backup data in .tsv files and upload them to Google Sheets"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('output_dir', nargs=1, type=str)
        parser.add_argument('-ng', '--no-google', action='store_true')

    def handle(self, *args, **options):
        output_dir = op.abspath(options.get('output_dir')[0])
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = op.join(output_dir, today)

        if not op.exists(output_dir):
            os.makedirs(output_dir)

        if not op.isdir(output_dir):
            self.stdout.write('Error: %s is not a directory' % output_dir)
            return

        sql_path = op.abspath(op.join(op.dirname(__file__), 'queries'))
        backup_tsv(sql_path, output_dir)
        if not options.get('no_google', None):
            upload_gsheets(output_dir)
