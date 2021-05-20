from time import time
import socket
import json
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa

from django.db import connection
from django.db.models import Subquery
from django.core.management.base import BaseCommand

from alyx.settings import TABLES_ROOT
from actions.models import Session
from data.models import Dataset, FileRecord

logger = logging.getLogger(__name__)


def measure_time(func):
    @wraps(func)
    def wrapper(*arg, **kwargs):
        t0 = time()
        res = func(*arg, **kwargs)
        logger.debug(f'{func.__name__} took {time() - t0:.2f} seconds to run')
        return res
    return wrapper


def _save(filename: Path, df: pd.DataFrame, metadata: dict = None) -> None:
    """
    Save pandas dataframe to parquet
    :param filename: Parquet save location
    :param df: A DataFrame to save as parquet table
    :param metadata: A dict of optional metadata
    :return:
    """
    # cf https://towardsdatascience.com/saving-metadata-with-dataframes-71f51f558d8e

    # from dataframe to parquet
    table = pa.Table.from_pandas(df)

    # Add user metadata
    table = table.replace_schema_metadata({
        'one_metadata': json.dumps(metadata or {}).encode(),
        **table.schema.metadata
    })

    # Save to parquet.
    pq.write_table(table, filename)


def _uuid2np(eids_uuid):
    return np.asfortranarray(
        np.array([np.frombuffer(eid.bytes, dtype=np.int64) for eid in eids_uuid]))


class Command(BaseCommand):
    """

    """
    help = "Generate ONE cache tables"
    dst_dir = None
    tables = None

    def add_arguments(self, parser):
        parser.add_argument('-D', '--destination', default=TABLES_ROOT,
                            help='File(s) destination')
        parser.add_argument('-t', '--tables', nargs='*', default=('sessions', 'datasets'),
                            help="List of tables to generate")
        parser.add_argument('--int-id', action='store_true',
                            help="Save uuids as ints")

    def handle(self, *_, **options):
        if options['verbosity'] < 1:
            logger.setLevel(logging.WARNING)
        if options['verbosity'] > 1:
            logger.setLevel(logging.DEBUG)
        self.dst_dir = Path(options.get('destination'))
        tables, int_id = options.get('tables'), options.get('int_id')
        self.generate_tables(tables, int_id=int_id)

    def generate_tables(self, tables, **kwargs) -> None:
        caches = dict()
        for table in tables:
            if table.lower() == 'sessions':
                logger.debug('Generating sessions DataFrame')
                caches[table] = generate_sessions_frame(**kwargs)
            elif table.lower() == 'datasets':
                logger.debug('Generating datasets DataFrame')
                caches[table] = generate_datasets_frame(**kwargs)
            else:
                raise ValueError(f'Unknown table "{table}"')
        self.save(**caches)

    def save(self, **kwargs) -> None:
        from zipfile import ZipFile
        self.dst_dir.mkdir(exist_ok=True)
        zip = ZipFile(self.dst_dir / 'cache.zip', 'w')
        metadata = create_metadata()
        jsonmeta = {}
        logger.info(f'Saving tables to {self.dst_dir}...')
        for name, df in kwargs.items():
            filename = self.dst_dir / f'{name}.pqt'  # Save to parquet
            _save(filename, df, metadata)
            zip.write(filename, filename.name)
            pqtinfo = pq.read_metadata(filename)
            jsonmeta[name] = {'nrecs': pqtinfo.num_rows, 'size': pqtinfo.serialized_size}
        # creates a json file containing metadata and add it to the zip file
        tag_file = self.dst_dir / 'cache_info.json'
        with open(tag_file, 'w') as fid:
            json.dump({**metadata, 'tables': jsonmeta}, fid, indent=1)
        zip.write(tag_file, tag_file.name)
        zip.close()


@measure_time
def generate_sessions_frame(int_id=True) -> pd.DataFrame:
    """SESSIONS_COLUMNS = (
        'id',               # uuid str
        'lab',              # str
        'subject',          # str
        'date',             # str yyyy-mm-dd
        'number',           # int64
        'task_protocol',    # str
        'project'           # str
    )
    """
    fields = ('id', 'lab__name', 'subject__nickname', 'start_time__date',
              'number', 'task_protocol', 'project__name')
    query = (Session
             .objects
             .select_related('subject', 'lab', 'project')
             .order_by('-start_time', 'subject__nickname', '-number'))  # FIXME Ignores nickname :(
    df = pd.DataFrame.from_records(query.values(*fields))
    # Rename, sort fields
    df = (
        (df
            .rename(lambda x: x.split('__')[0], axis=1)
            .rename({'start_time': 'date'}, axis=1)
            .dropna(subset=['number', 'date', 'subject', 'lab'])  # Remove dud or base sessions
            .sort_values(['date', 'subject', 'number'], ascending=False))
    )
    df['number'] = df['number'].astype(int)  # After dropping nans we can convert number to int
    # These columns may be empty; ensure None -> ''
    for col in ('task_protocol', 'project'):
        df[col] = df[col].astype(str)

    if int_id:
        # Convert UUID objects to 2xint64
        df[['id_0', 'id_1']] = _uuid2np(df['id'].values)
        df = (
            (df
                .drop('id', axis=1)
                .set_index(['id_0', 'id_1']))
        )
    else:
        # Convert UUID objects to str: not supported by parquet
        df['id'] = df['id'].astype(str)
        df.set_index('id', inplace=True)

    return df


@measure_time
def generate_datasets_frame(int_id=True) -> pd.DataFrame:
    """DATASETS_COLUMNS = (
        'id',               # uuid str
        'eid',              # uuid str
        'session_path',     # relative to the root
        'rel_path',         # relative to the session path, includes the filename
        'file_size',        # float, bytes, optional
        'hash',             # sha1/md5 str, recomputed in load function
        'exists'            # bool
    )
    """
    fields = ('id', 'session', 'file_size', 'hash', 'file_records__relative_path',
              'file_records__data_repository__globus_path', 'default_dataset')
    # Find all online file records
    records = FileRecord.objects.filter(data_repository__globus_is_personal=False, exists=True)
    query = (
        (Dataset
            .objects
            .select_related('file_records')
            .filter(file_records__in=Subquery(records.values('id'))))
    )
    df = pd.DataFrame.from_records(query.values(*fields))
    # NB: Splitting and re-joining all these strings is slow :(
    paths = df.file_records__relative_path.str.split('/', n=3, expand=True)
    globus_path = df['file_records__data_repository__globus_path']  # /lab/Subjects/
    session_path = paths[0].str.cat(paths.iloc[:, 1:3], sep='/')  # subject/date/number
    df['rel_path'] = paths.iloc[:, -1]  # collection/revision/filename
    df['session_path'] = (globus_path + session_path).str.strip('/')  # full path relative to root
    df['exists'] = True
    df = (
        (df
            .filter(regex=r'^(?!file_records).*', axis=1)  # drop file record fields
            .rename({'session': 'eid', 'default_dataset': 'default_revision'}, axis=1)))

    if int_id:
        # Convert UUID objects to 2xint64
        df[['id_0', 'id_1']] = _uuid2np(df['id'].values)
        df[['eid_0', 'eid_1']] = _uuid2np(df['eid'].values)
        df = (
            (df
                .drop(['id', 'eid'], axis=1)
                .set_index(['id_0', 'id_1'])
                .sort_index())
        )
    else:
        # Convert UUIDs to str: not supported by parquet
        df[['id', 'eid']] = df[['id', 'eid']].astype(str)
        df = df.set_index('id').sort_index()

    return df


def create_metadata() -> dict:
    """Create ONE metadata dictionary"""
    return {
        'date_created': datetime.now().isoformat(sep=' ', timespec='minutes'),
        'origin': connection.settings_dict['NAME'] or socket.gethostname(),
    }


def update_table_metadata(table: pa.Table, metadata: dict) -> pa.Table:
    """Add ONE metadata to parquet table"""
    # Add user metadata
    return table.replace_schema_metadata({
        'one_metadata': json.dumps(metadata or {}).encode(),
        **table.schema.metadata
    })
