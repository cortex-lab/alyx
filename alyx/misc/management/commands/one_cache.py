from time import time
import io
import socket
import json
import logging
from pathlib import Path
import urllib.parse
from datetime import datetime
from functools import wraps
from sys import getsizeof
import zipfile
import tempfile
import re

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa

from django.db import connection
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator

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


def _s3_filesystem(**kwargs) -> pa.fs.S3FileSystem:
    """
    Get S3 FileSystem object.  Order of credential precedence:

    1. kwargs
    2. S3_ACCESS dict in settings_secret.py
    3. Default aws cli credentials

    :param kwargs: see pyarrow.fs.S3FileSystem
    :return: A FileSystem object with the given credentials
    """
    try:
        from alyx.settings_secret import S3_ACCESS
    except ImportError:
        S3_ACCESS = {}
    S3_ACCESS.update(kwargs)
    return pa.fs.S3FileSystem(**S3_ACCESS)


def _get_s3_virtual_host(uri, region) -> str:
    """
    Convert a given bucket URI to a URL by

    S3 documentation:
    https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-bucket-intro.html#virtual-host-style-url-ex

    :param uri: The bucket name or full path URI
    :param region: The region, e.g. eu-west-1
    :return: The Web URL (virtual host name and https scheme)
    """
    assert region and re.match(r'\w{2}-\w+-[1-3]', region)
    parsed = urllib.parse.urlparse(uri)  # remove scheme if necessary
    key = parsed.path.strip('/').split('/')
    bucket = parsed.netloc or key.pop(0)
    hostname = f"{bucket}.{parsed.scheme or 's3'}.{region}.amazonaws.com"
    return 'https://' + '/'.join((hostname, *key))


def _save(filename: str, df: pd.DataFrame, metadata: dict = None, dry=False) -> pa.Table:
    """
    Save pandas dataframe to parquet.

    If using S3, by default the aws default credentials are used.  These may be overridden by the
    S3_ACCESS dict in settings_secret.py.

    :param filename: Parquet save location, may be local file path or S3 location
    :param df: A DataFrame to save as parquet table
    :param metadata: A dict of optional metadata
    :param dry: if True, return pyarrow table without saving to disk
    :return: the saved pyarrow table
    """
    # cf https://towardsdatascience.com/saving-metadata-with-dataframes-71f51f558d8e

    # from dataframe to parquet
    table = pa.Table.from_pandas(df)

    # Add user metadata
    table = table.replace_schema_metadata({
        'one_metadata': json.dumps(metadata or {}).encode(),
        **table.schema.metadata
    })

    if not dry:
        parsed = urllib.parse.urlparse(filename)
        if parsed.scheme == 's3':
            # Filename mustn't include scheme
            pq.write_table(table, parsed.path, filesystem=_s3_filesystem())
        elif parsed.scheme == '':
            pq.write_table(table, filename)
        else:
            raise ValueError(f'Unsupported URI scheme "{parsed.scheme}"')
    return table


def _uuid2np(eids_uuid):
    return np.asfortranarray(
        np.array([np.frombuffer(eid.bytes, dtype=np.int64) for eid in eids_uuid]))


class Command(BaseCommand):
    """
    NB: When compress flag is passed, all tables are expected to fit into memory together.
    """
    help = "Generate ONE cache tables"
    dst_dir = None
    tables = None
    metadata = None
    compress = None

    def add_arguments(self, parser):
        parser.add_argument('-D', '--destination', default=TABLES_ROOT,
                            help='File(s) destination')
        parser.add_argument('-t', '--tables', nargs='*', default=('sessions', 'datasets'),
                            help="List of tables to generate")
        parser.add_argument('--int-id', action='store_true',
                            help="Save uuids as ints")
        parser.add_argument('--compress', action='store_true',
                            help="Save files into compressed folder")

    def handle(self, *_, **options):
        if options['verbosity'] < 1:
            logger.setLevel(logging.WARNING)
        if options['verbosity'] > 1:
            logger.setLevel(logging.DEBUG)
        self.dst_dir = options.get('destination')
        self.compress = options.get('compress')
        tables, int_id = options.get('tables'), options.get('int_id')
        self.generate_tables(tables, int_id=int_id)

    def generate_tables(self, tables, **kwargs) -> list:
        """
        Generate and save a list of tables.  Supported tables include 'sessions' and 'datasets'.
        :param tables: A tuple of table names.
        :param kwargs:
        :return: A list of paths to the saved files
        """
        self.metadata = create_metadata()
        to_compress = {}
        dry = self.compress
        for table in tables:
            if table.lower() == 'sessions':
                logger.debug('Generating sessions DataFrame')
                tbl, filename = self._save_table(generate_sessions_frame(**kwargs), table, dry=dry)
                to_compress[filename] = tbl
            elif table.lower() == 'datasets':
                logger.debug('Generating datasets DataFrame')
                tbl, filename = self._save_table(generate_datasets_frame(**kwargs), table, dry=dry)
                to_compress[filename] = tbl
            else:
                raise ValueError(f'Unknown table "{table}"')

        if self.compress:
            return list(self._compress_tables(to_compress))
        else:
            return list(to_compress.keys())

    def _save_table(self, table, name, **kwargs):
        """Save a given table to <dst_dir>/<name>.pqt.

        Given a table name and a pandas DataFrame, save as parquet table to disk.  If dst_dir
        attribute is an s3 URI, the table is saved directly there

        :param table: the pandas DataFrame to save
        :param name: table name
        :param dry: If True, does not actually write to disk
        :return: A PyArrow table and the full path to the saved file
        """
        if not kwargs.get('dry'):
            logger.info(f'Saving table "{name}" to {self.dst_dir}...')
        scheme = urllib.parse.urlparse(self.dst_dir).scheme or 'file'
        if scheme == 'file':
            Path(self.dst_dir).mkdir(exist_ok=True)
            filename = Path(self.dst_dir) / f'{name}.pqt'  # Save to parquet
        else:
            filename = self.dst_dir.strip('/') + f'/{name}.pqt'  # Save to parquet
        pa_table = _save(str(filename), table, self.metadata, **kwargs)
        return pa_table, str(filename)

    def _compress_tables(self, table_map) -> tuple:
        """
        Write cache_info JSON and create zip file comprising parquet tables + JSON

        :param table_map: a dict of filenames and corresponding
        :return:
        """
        ZIP_NAME = 'cache.zip'
        META_NAME = 'cache_info.json'

        logger.info('Compressing tables...')  # Write zip in memory
        zip_buffer = io.BytesIO()  # Mem buffer to store compressed table data
        with tempfile.TemporaryDirectory() as tmp, \
                zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip:
            jsonmeta = {}
            for filename, table in table_map.items():
                tmp_filename = Path(tmp) / Path(filename).name  # Table filename in temp dir
                pq.write_table(table, tmp_filename)  # Write table to tempdir
                zip.write(tmp_filename, Path(filename).name)  # Load and compress
                pqtinfo = pq.read_metadata(tmp_filename)  # Load metadata for cache_info file
                jsonmeta[Path(filename).stem] = {
                    'nrecs': pqtinfo.num_rows,
                    'size': pqtinfo.serialized_size
                }
            metadata = {**self.metadata, 'tables': jsonmeta}
            zip.writestr(META_NAME, json.dumps(metadata, indent=1))  # Compress cache info

        logger.info('Writing to file...')
        parsed = urllib.parse.urlparse(self.dst_dir)
        scheme = parsed.scheme or 'file'
        try:
            if scheme == 's3':
                zip_file = f'{parsed.path.strip("/")}/{ZIP_NAME}'
                tag_file = f'{parsed.path.strip("/")}/{META_NAME}'
                s3 = _s3_filesystem()
                metadata['location'] = _get_s3_virtual_host(zip_file, s3.region)  # Add URL
                # Write cache info json to s3
                with s3.open_output_stream(tag_file) as stream:
                    stream.writelines(json.dumps(metadata, indent=1))
                # Write zip file to s3
                with s3.open_output_stream(zip_file) as stream:
                    stream.write(zip_buffer.getbuffer())
            elif scheme == 'file':
                # creates a json file containing metadata and add it to the zip file
                tag_file = Path(self.dst_dir) / META_NAME
                zip_file = Path(self.dst_dir) / ZIP_NAME
                with open(tag_file, 'w') as fid:
                    json.dump(metadata, fid, indent=1)
                with open(zip_file, 'wb') as fid:
                    fid.write(zip_buffer.getbuffer())
            else:
                raise ValueError(f'Unsupported URI scheme "{scheme}"')
        finally:
            zip_buffer.close()
        return zip_file, tag_file


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
