from time import time
import io
import socket
import json
import logging
from pathlib import Path
import urllib.parse
from functools import wraps
from sys import getsizeof
import zipfile
import tempfile

import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from iblutil.io.parquet import uuid2np
from one.alf.cache import _metadata
from one.remote.aws import get_s3_virtual_host

from django.db import connection
from django.db.models import Q, Exists, OuterRef
from django.core.management.base import BaseCommand
from django.contrib.postgres.aggregates import ArrayAgg

from alyx.settings import TABLES_ROOT
from actions.models import Session
from data.models import Dataset, FileRecord
from experiments.models import ProbeInsertion

logger = logging.getLogger(__name__)
ONE_API_VERSION = '1.13.0'  # Minimum compatible ONE api version


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


def _save(filename: str, df: pd.DataFrame, metadata: dict = None, dry=False) -> pa.Table:
    """
    Save pandas dataframe to parquet.

    If using S3, by default the aws default credentials are used.  These may be overridden by the
    S3_ACCESS dict in settings_secret.py.

    :param filename: Parquet save location, may be local file path or S3 location (starting s3://)
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
                            help='File(s) destination, may be local path or s3 URI starting s3://')
        parser.add_argument('-t', '--tables', nargs='*', default=('sessions', 'datasets'),
                            help="List of tables to generate")
        parser.add_argument('--int-id', action='store_true',
                            help="Save uuids as ints")
        parser.add_argument('--compress', action='store_true',
                            help="Save files into compressed folder")
        parser.add_argument('--tag', nargs='*',
                            help="List of tag names to filter datasets by")
        parser.add_argument('--qc', action='store_true',
                            help="Save QC fields to a JSON file")

    def handle(self, *_, **options):
        if options['verbosity'] < 1:
            logger.setLevel(logging.WARNING)
        if options['verbosity'] > 1:
            logger.setLevel(logging.DEBUG)
        self.dst_dir = options.get('destination')
        self.compress = options.get('compress')
        tables, int_id, qc = options.get('tables'), options.get('int_id'), options.get('qc')
        self.generate_tables(tables, int_id=int_id, export_qc=qc, tags=options.get('tag'))

    def generate_tables(self, tables, export_qc=False, **kwargs) -> list:
        """
        Generate and save a list of tables.  Supported tables include 'sessions' and 'datasets'.
        :param tables: A tuple of table names.
        :param export_qc: If true, the extended QC will be saved to a JSON file.
        :param kwargs: Arguments to pass to cache generation functions.
        :return: A list of paths to the saved files.
        """
        self.metadata = create_metadata()
        if kwargs.get('tags'):
            self.metadata['database_tags'] = kwargs.get('tags')
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

        if export_qc:
            tbl, filename = self._save_qc(dry=dry, tags=kwargs.get('tags'))
            to_compress[filename] = tbl

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

    @measure_time
    def _save_qc(self, dry=False, tags=None):
        sessions = Session.objects.all()
        if tags:
            if not isinstance(tags, str):
                sessions = sessions.filter(data_dataset_session_related__tags__name__in=tags)
            else:
                sessions = sessions.filter(data_dataset_session_related__tags__name=tags)
        qc = list(sessions.values('pk', 'qc', 'extended_qc').distinct())
        outcome_map = dict(Session.QC_CHOICES)
        for d in qc:  # replace enumeration int with string
            d['eid'] = str(d.pop('pk'))  # rename field
            d['qc_outcome'] = outcome_map[d.pop('qc')]
            d['extended_qc'] = d.pop('extended_qc')  # pop to preserve order
        logger.debug('Fetched %i QC records', len(qc))

        # Fetch insertion QC
        insertions = ProbeInsertion.objects.all()
        if tags:
            if not isinstance(tags, str):
                insertions = insertions.filter(
                    session__data_dataset_session_related__tags__name__in=tags)
            else:
                insertions = insertions.filter(
                    session__data_dataset_session_related__tags__name=tags)
        qc_ins = list(insertions.values('pk', 'name', 'json', 'session__pk').distinct())

        # Collate with session QC list
        for ins in qc_ins:
            if 'extended_qc' not in ins['json']:
                continue
            d = next(x for x in qc if x['eid'] == str(ins['session__pk']))
            d.setdefault('probe_insertions', []).append({
                'pid': str(ins.pop('pk')),
                'probe_name': ins.pop('name'),
                'qc_outcome': ins['json'].pop('qc', 'NOT_SET'),
                'extended_qc': ins['json'].pop('extended_qc')
            })

        filename = self.dst_dir.strip('/') + '/QC.json'  # Save to JSON
        if not dry:
            with open(filename, 'w') as fp:
                json.dump(qc, fp)
        return qc, str(filename)

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
                ext = Path(filename).suffix
                if ext == '.pqt':
                    pq.write_table(table, tmp_filename)  # Write table to tempdir
                    zip.write(tmp_filename, Path(filename).name)  # Load and compress
                    pqtinfo = pq.read_metadata(tmp_filename)  # Load metadata for cache_info file
                    jsonmeta[Path(filename).stem] = {
                        'nrecs': pqtinfo.num_rows,
                        'size': pqtinfo.serialized_size
                    }
                elif ext == '.json':
                    with open(tmp_filename, 'w') as fp:
                        json.dump(table, fp)
                    zip.write(tmp_filename, Path(filename).name)
                else:
                    raise NotImplementedError(f'Unable to save table with extension "{ext}"')
            metadata = {**self.metadata, 'tables': jsonmeta}
            zip.writestr(META_NAME, json.dumps(metadata, indent=1))  # Compress cache info

        logger.info('Writing to file...')
        parsed = urllib.parse.urlparse(self.dst_dir)
        scheme = parsed.scheme or 'file'
        try:
            if scheme == 's3':
                zip_file = f'{parsed.netloc}/{parsed.path.strip("/")}/{ZIP_NAME}'
                tag_file = f'{parsed.netloc}/{parsed.path.strip("/")}/{META_NAME}'
                s3 = _s3_filesystem()
                metadata['location'] = get_s3_virtual_host(zip_file, s3.region)  # Add URL
                # Write cache info json to s3
                logger.debug(f'Opening output stream to {tag_file}')
                with s3.open_output_stream(tag_file) as stream:
                    stream.write(json.dumps(metadata, indent=1).encode())
                # Write zip file to s3
                logger.debug(f'Opening output stream to {zip_file}')
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
def generate_sessions_frame(int_id=True, tags=None) -> pd.DataFrame:
    """SESSIONS_COLUMNS = (
        'id',               # uuid str
        'lab',              # str
        'subject',          # str
        'date',             # str yyyy-mm-dd
        'number',           # int64
        'task_protocol',    # str
        'projects'           # str
    )
    """
    fields = ('id', 'lab__name', 'subject__nickname', 'start_time__date',
              'number', 'task_protocol', 'all_projects')
    query = (Session
             .objects
             .select_related('subject', 'lab')
             .prefetch_related('projects')
             .annotate(all_projects=ArrayAgg('projects__name'))
             .order_by('-start_time', 'subject__nickname', '-number'))  # FIXME Ignores nickname :(
    if tags:
        if not isinstance(tags, str):
            query = query.filter(data_dataset_session_related__tags__name__in=tags)
        else:
            query = query.filter(data_dataset_session_related__tags__name=tags)
    df = pd.DataFrame.from_records(query.values(*fields).distinct())
    logger.debug(f'Raw session frame = {getsizeof(df) / 1024**2} MiB')
    # Rename, sort fields
    df['all_projects'] = df['all_projects'].map(lambda x: ','.join(filter(None, set(x))))
    df = (
        (df
            .rename(lambda x: x.split('__')[0], axis=1)
            .rename({'start_time': 'date', 'all_projects': 'projects'}, axis=1)
            .dropna(subset=['number', 'date', 'subject', 'lab'])  # Remove dud or base sessions
            .sort_values(['date', 'subject', 'number'], ascending=False))
    )
    df['number'] = df['number'].astype(int)  # After dropping nans we can convert number to int
    # These columns may be empty; ensure None -> ''
    for col in ('task_protocol', 'projects'):
        df[col] = df[col].astype(str)

    if int_id:
        # Convert UUID objects to 2xint64
        df[['id_0', 'id_1']] = uuid2np(df['id'].values)
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
def generate_datasets_frame(int_id=True, tags=None) -> pd.DataFrame:
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
    # Determine which file records are on AWS and which are on FlatIron
    fr = FileRecord.objects.select_related('data_repository')
    on_flatiron = fr.filter(dataset=OuterRef('pk'),
                            exists=True,
                            data_repository__name__startswith='flatiron').values('pk')
    on_aws = fr.filter(dataset=OuterRef('pk'),
                       exists=True,
                       data_repository__name__startswith='aws').values('pk')
    # Fetch datasets and their related tables
    ds = Dataset.objects.select_related('session', 'session__subject', 'session__lab', 'revision')
    if tags:
        kw = {'tags__name__in' if not isinstance(tags, str) else 'tags__name': tags}
        ds = ds.prefetch_related('tag').filter(**kw)
    # Filter out datasets that do not exist on either repository
    ds = ds.annotate(exists_flatiron=Exists(on_flatiron), exists_aws=Exists(on_aws))
    ds = ds.filter(Q(exists_flatiron=True) | Q(exists_aws=True))

    # fields to keep from Dataset table
    fields = (
        'id', 'name', 'file_size', 'hash', 'collection', 'revision__name', 'default_dataset',
        'session__id', 'session__start_time__date', 'session__number',
        'session__subject__nickname', 'session__lab__name', 'exists_flatiron', 'exists_aws'
    )
    fields_map = {'session__id': 'eid', 'default_dataset': 'default_revision'}
    df = pd.DataFrame.from_records(ds.values(*fields)).rename(fields_map, axis=1)
    df['exists'] = True

    # TODO New version without this nonsense
    # session_path
    globus_path = df.pop('session__lab__name') + '/Subjects'
    subject = df.pop('session__subject__nickname')
    date = df.pop('session__start_time__date').astype(str)
    number = df.pop('session__number').apply(lambda x: str(x).zfill(3))
    df['session_path'] = globus_path.str.cat((subject, date, number), sep='/')

    # relative_path
    revision = map(lambda x: None if not x else f'#{x}#', df.pop('revision__name'))
    zipped = zip(df.pop('collection'), revision, df.pop('name'))
    df['rel_path'] = ['/'.join(filter(None, x)) for x in zipped]

    if int_id:
        # Convert UUID objects to 2xint64
        df[['id_0', 'id_1']] = uuid2np(df['id'].values)
        df[['eid_0', 'eid_1']] = uuid2np(df['eid'].values)
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
    meta = _metadata(connection.settings_dict['NAME'] or socket.gethostname())
    meta['min_api_version'] = ONE_API_VERSION
    return meta


def update_table_metadata(table: pa.Table, metadata: dict) -> pa.Table:
    """Add ONE metadata to parquet table"""
    # Add user metadata
    return table.replace_schema_metadata({
        'one_metadata': json.dumps(metadata or {}).encode(),
        **table.schema.metadata
    })
