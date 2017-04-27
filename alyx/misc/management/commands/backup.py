import csv
from datetime import datetime
import glob
import logging
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


def exec_sql(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)


def backup_tsv(sql_dir, output_dir):
    today = datetime.now().strftime("%Y-%m-%d")
    path = op.abspath(op.join(sql_dir, '*.sql'))
    files = sorted(glob.glob(path))
    for file in files:
        with open(file, 'r') as f:
            sql = f.read()
        name = op.splitext(op.basename(file))[0]
        path = op.abspath(op.join(output_dir, today, name + '.tsv'))
        if not os.path.exists(op.dirname(path)):
            os.makedirs(op.dirname(path))
        logger.info("Dumping %s to %s.", name, path)
        cmd = ("copy (%s) to '%s' with CSV DELIMITER E'\t' header encoding 'utf-8'" %
               (sql, path))
        exec_sql(cmd)


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
    cell_list = ws.range('A2:%s%d' % (last_col, n_rows + 1))
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
    last = sorted(os.listdir(output_dir))
    if not last:
        logger.warn("There are no backups in %s.", output_dir)
        return
    last = last[-1]
    files = sorted(glob.glob(op.join(output_dir, last, '*.tsv')))
    logger.info("Found %d files in %s.", len(files), op.join(output_dir, last))
    doc = gc.open('Alyx Backup')
    for path in files:
        name = op.splitext(op.basename(path))[0]
        n = upload_table(doc, path)
        logger.info("%d items uploaded to `%s` sheet of Google Sheet backup document.",
                    n, name)


class Command(BaseCommand):
    help = "Backup data in .tsv files and upload them to Google Sheets"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('output_dir', nargs=1, type=str)

    def handle(self, *args, **options):
        output_dir = op.abspath(options.get('output_dir')[0])

        if not op.isdir(output_dir):
            self.stdout.write('Error: %s is not a directory' % output_dir)
            return

        sql_path = op.abspath(op.join(op.dirname(__file__), 'queries'))
        backup_tsv(sql_path, output_dir)
        upload_gsheets(output_dir)
