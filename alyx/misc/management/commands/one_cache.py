import json
import logging
import socket
from datetime import datetime
from functools import wraps
from pathlib import Path
from sys import getsizeof
from time import time

import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
from actions.models import Session
from alyx.settings import TABLES_ROOT
from data.models import Dataset, FileRecord
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.db import connection

logger = logging.getLogger(__name__)


def measure_time_and_mem_use(func):
    @wraps(func)
    def wrapper(*arg, **kwargs):
        t0 = time()
        res = func(*arg, **kwargs)
        mem_use = psutil.Process().memory_info().rss / (1024 * 1024 * 1024)  # measure in GB
        logger.debug(f'{func.__name__} took {time() - t0:.2f} seconds to run and is consuming '
                     f'{mem_use} GB of resident memory (not always accurate)')
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
    metadata = None

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
        self.metadata = create_metadata()
        for table in tables:
            if table.lower() == 'sessions':
                logger.debug('Generating sessions DataFrame')
                self._save_table(generate_sessions_frame(**kwargs), table)
            elif table.lower() == 'datasets':
                logger.debug('Generating datasets DataFrame')
                self._save_table(generate_datasets_frame(**kwargs), table)
            else:
                raise ValueError(f'Unknown table "{table}"')
        self._compress_tables()

    def _save_table(self, table, name):
        self.dst_dir.mkdir(exist_ok=True)
        logger.info(f'Saving table "{name}" to {self.dst_dir}...')
        filename = self.dst_dir / f'{name}.pqt'  # Save to parquet
        _save(filename, table, self.metadata)

    def _compress_tables(self) -> None:
        """Write cache_info JSON and create zip file comprising parquet tables + JSON"""
        from zipfile import ZipFile
        zip = ZipFile(self.dst_dir / 'cache.zip', 'w')
        jsonmeta = {}
        logger.info(f'Compressing tables to {zip.filename}...')
        for filename in self.dst_dir.glob('*.pqt'):
            zip.write(filename, filename.name)
            pqtinfo = pq.read_metadata(filename)
            jsonmeta[filename.stem] = {'nrecs': pqtinfo.num_rows, 'size': pqtinfo.serialized_size}
        # creates a json file containing metadata and add it to the zip file
        tag_file = self.dst_dir / 'cache_info.json'
        with open(tag_file, 'w') as fid:
            json.dump({**self.metadata, 'tables': jsonmeta}, fid, indent=1)
        zip.write(tag_file, tag_file.name)
        write_fail = zip.testzip()
        zip.close()
        if write_fail:
            logger.error(f'Failed to compress {write_fail}')


@measure_time_and_mem_use
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
    logger.debug(f'Raw session frame = {getsizeof(df) / 1024**2} MiB')
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

    logger.debug(f'Final session frame = {getsizeof(df) / 1024 ** 2:.1f} MiB')
    return df


@measure_time_and_mem_use
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
    # Find all online file records
    batch_size = 50000
    qs = Dataset.objects.all().order_by('created_datetime')
    paginator = Paginator(qs, batch_size)

    # fields to keep from Dataset table
    dataset_fields = ('id', 'session', 'file_size', 'hash', 'default_dataset')
    # fields to keep from FileRecord table
    filerecord_fields = ('dataset_id', 'relative_path', 'exists', 'data_repository__name',
                         'data_repository__globus_path')

    all_df = []
    for i in paginator.page_range:
        data = paginator.get_page(i)
        current_qs = data.object_list
        df = pd.DataFrame.from_records(current_qs.values(*dataset_fields))
        frs = FileRecord.objects.select_related('data_repository').\
            filter(dataset_id__in=df['id'].values, exists=True,
                   data_repository__globus_is_personal=False)
        fr = pd.DataFrame.from_records(frs.values(*filerecord_fields))
        df = df.set_index('id').join(fr.set_index('dataset_id'))
        all_df.append(df)

    df = pd.concat(all_df, ignore_index=False)
    del all_df

    df = df.sort_index().sort_values('data_repository__name', kind='mergesort')
    # Remove datasets where no file records exist
    df.dropna(subset=('exists', 'relative_path'), inplace=True)
    df['exists_aws'] = df['data_repository__name'].str.startswith('aws')
    exists_aws = df.groupby(level=0)['exists_aws'].any()  # Any associated file records are AWS
    # Sorted by data repository name, this should select the flatiron records
    df = df.groupby(level=0).last()
    df.update(exists_aws)
    del exists_aws
    # NB: Splitting and re-joining all these strings is slow :(
    paths = df.pop('relative_path').str.split('/', n=3, expand=True)
    globus_path = df['data_repository__globus_path']  # /lab/Subjects/
    session_path = paths[0].str.cat(paths.iloc[:, 1:3], sep='/')  # subject/date/number
    df['relative_path'] = paths.iloc[:, -1]  # collection/revision/filename
    df['session_path'] = (globus_path + session_path).str.strip('/')  # full path relative to root
    del paths, session_path
    fields_map = {
        'session': 'eid',
        'default_dataset': 'default_revision',
        'relative_path': 'rel_path',
        'index': 'id'}
    df = (
        (df
            .filter(regex=r'^(?!data_repository).*', axis=1)  # drop file record fields
            .reset_index()
            .rename(fields_map, axis=1)))
    if int_id:
        # Convert UUID objects to 2xint64
        df[['id_0', 'id_1']] = _uuid2np(df['id'].values)
        df[['eid_0', 'eid_1']] = _uuid2np(df['eid'].values)
        df = (
            (df
                .drop(['id', 'eid'], axis=1)
                .set_index(['eid_0', 'eid_1', 'id_0', 'id_1'])
                .sort_index())
        )
    else:
        # Convert UUIDs to str: not supported by parquet
        df[['id', 'eid']] = df[['id', 'eid']].astype(str)
        df = df.set_index(['eid', 'id']).sort_index()

    logger.debug(f'Final datasets frame = {getsizeof(df) / 1024 ** 2:.1f} MiB')
    return df


def create_metadata() -> dict:
    """Create ONE metadata dictionary"""
    return {
        'date_created': datetime.now().isoformat(sep=' ', timespec='minutes'),
        'origin': connection.settings_dict['NAME'] or socket.gethostname(),
        'min_api_version': '1.8.0'
    }


def update_table_metadata(table: pa.Table, metadata: dict) -> pa.Table:
    """Add ONE metadata to parquet table"""
    # Add user metadata
    return table.replace_schema_metadata({
        'one_metadata': json.dumps(metadata or {}).encode(),
        **table.schema.metadata
    })
