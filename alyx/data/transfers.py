import json
import logging
import os
import os.path as op
import re

import globus_sdk
from django.db.models.functions import Length

from alyx import settings
from data.models import FileRecord, Dataset, DatasetType, DataFormat

logger = logging.getLogger(__name__)


# Login
# ------------------------------------------------------------------------------------------------

def get_config_path(path=''):
    path = op.expanduser(op.join('~/.alyx', path))
    os.makedirs(op.dirname(path), exist_ok=True)
    return path


def create_globus_client():
    client = globus_sdk.NativeAppAuthClient(settings.GLOBUS_CLIENT_ID)
    client.oauth2_start_flow(refresh_tokens=True)
    return client


def create_globus_token():
    client = create_globus_client()
    print('Please go to this URL and login: {0}'
          .format(client.oauth2_get_authorize_url()))
    get_input = getattr(__builtins__, 'raw_input', input)
    auth_code = get_input('Please enter the code here: ').strip()
    token_response = client.oauth2_exchange_code_for_tokens(auth_code)
    globus_transfer_data = token_response.by_resource_server['transfer.api.globus.org']

    data = dict(transfer_rt=globus_transfer_data['refresh_token'],
                transfer_at=globus_transfer_data['access_token'],
                expires_at_s=globus_transfer_data['expires_at_seconds'],
                )
    path = get_config_path('globus-token.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)


# Data transfer
# ------------------------------------------------------------------------------------------------

def get_globus_transfer_rt():
    path = get_config_path('globus-token.json')
    if not op.exists(path):
        return
    with open(path, 'r') as f:
        return json.load(f).get('transfer_rt', None)


def globus_transfer_client():
    transfer_rt = get_globus_transfer_rt()
    if not transfer_rt:
        create_globus_token()
        transfer_rt = get_globus_transfer_rt()
    client = create_globus_client()
    authorizer = globus_sdk.RefreshTokenAuthorizer(transfer_rt, client)
    tc = globus_sdk.TransferClient(authorizer=authorizer)
    return tc


def _escape_label(label):
    return re.sub(r'[^a-zA-Z0-9 \-]', '-', label)


def _get_absolute_path(file_record):
    path1 = file_record.data_repository.globus_path
    path2 = file_record.relative_path
    path2 = path2.replace('\\', '/')
    # HACK
    if path2.startswith('Data2/'):
        path2 = path2[6:]
    if path2.startswith('/'):
        path2 = path2[1:]
    path = op.join(path1, path2)
    return path


def _incomplete_dataset_ids():
    return FileRecord.objects.filter(exists=False).values_list('dataset', flat=True).distinct()


def _add_uuid_to_filename(fn, uuid):
    dpath, ext = op.splitext(fn)
    return dpath + '.' + str(uuid) + ext


def start_globus_transfer(source_file_id, destination_file_id, dry_run=False):
    """Start a globus file transfer between two file record UUIDs."""
    source_fr = FileRecord.objects.get(pk=source_file_id)
    destination_fr = FileRecord.objects.get(pk=destination_file_id)

    source_id = source_fr.data_repository.globus_endpoint_id
    destination_id = destination_fr.data_repository.globus_endpoint_id

    if not source_id and not destination_id:
        raise ValueError("The Globus endpoint ids of source and destination must be set.")

    source_path = _get_absolute_path(source_fr)
    destination_path = _get_absolute_path(destination_fr)

    # Add dataset UUID.
    destination_path = _add_uuid_to_filename(destination_path, source_fr.dataset.pk)

    label = 'Transfer %s from %s to %s' % (
        _escape_label(op.basename(destination_path)),
        source_fr.data_repository.name,
        destination_fr.data_repository.name,
    )
    tc = globus_transfer_client()
    tdata = globus_sdk.TransferData(
        tc, source_id, destination_id, verify_checksum=True, sync_level='checksum',
        label=label,
    )
    tdata.add_item(source_path, destination_path)

    logger.info("Transfer from %s <%s> to %s <%s>%s.",
                source_fr.data_repository.name, source_path,
                destination_fr.data_repository.name, destination_path,
                ' (dry)' if dry_run else '')

    if dry_run:
        return

    response = tc.submit_transfer(tdata)

    task_id = response.get('task_id', None)
    message = response.get('message', None)
    # code = response.get('code', None)

    logger.info("%s (task UUID: %s)", message, task_id)
    return response


def globus_file_exists(file_record):
    tc = globus_transfer_client()
    path = _get_absolute_path(file_record)
    dir_path = op.dirname(path)
    name = op.basename(path)
    name_uuid = _add_uuid_to_filename(name, file_record.dataset.pk)
    try:
        existing = tc.operation_ls(file_record.data_repository.globus_endpoint_id, path=dir_path)
    except globus_sdk.exc.TransferAPIError as e:
        logger.warn(e)
        return False
    for existing_file in existing:
        if existing_file['name'] in (name, name_uuid) and existing_file['size'] > 0:
            return True
    return False


def _get_data_type_format(filename):
    """Return the DatasetType and DataFormat associated to an ALF filename."""

    dataset_type = None
    # NOTE: we sort by decreasing filename_pattern length, so that longer (more specific) alf
    # filenames are chosen. For example, foo.bar.* has higher priority than foo.*.* because
    # its length is higher. For 1-character-long parts, we use the fact that * < any character
    # which is why we sort by decreasing filename_pattern.
    for dt in (DatasetType.objects.filter(filename_pattern__isnull=False).
               order_by(Length('filename_pattern').desc(), '-filename_pattern')):
        if not dt.filename_pattern.strip():
            continue
        reg = dt.filename_pattern.replace('.', r'\.').replace('*', r'[^\.]+')
        if re.match(reg, filename):
            dataset_type = dt
            break

    data_format = None
    for df in DataFormat.objects.filter(filename_pattern__isnull=False):
        reg = df.filename_pattern.replace('.', r'\.').replace('*', r'[^\.]+')
        if not df.filename_pattern.strip():
            continue
        if re.match(reg, filename):
            data_format = df
            break

    return dataset_type, data_format


def _get_repositories_for_projects(projects):
    # List of data repositories associated to the subject's projects.
    repositories = set()
    for project in projects:
        repositories.update(project.repositories.all())
    return list(repositories)


def _create_dataset_file_records(
        rel_dir_path=None, filename=None, session=None, user=None,
        repositories=None, exists_in=None):

    relative_path = op.join(rel_dir_path, filename)
    dataset_type, data_format = _get_data_type_format(filename)
    if not dataset_type:
        logger.warn("No dataset type found for %s", filename)
    if not data_format:
        logger.warn("No data format found for %s", filename)

    # Create the dataset.
    dataset, _ = Dataset.objects.get_or_create(
        name=filename, session=session, created_by=user,
        dataset_type=dataset_type, data_format=data_format)
    dataset.full_clean()

    # Create the parent datasets, according to the parent dataset types.
    if dataset_type:
        dst = dataset_type.parent_dataset_type
        ds = dataset
        while dst is not None:
            ds.parent_dataset = Dataset.objects.get_or_create(
                session=session, created_by=user, dataset_type=dst)[0]
            ds.save()

            dst = dst.parent_dataset_type
            ds = ds.parent_dataset

    # Create one file record per repository.
    exists_in = exists_in or ()
    for repo in repositories:
        exists = repo in exists_in
        # Do not create a new file record if it already exists.
        fr, _ = FileRecord.objects.get_or_create(
            dataset=dataset, data_repository=repo, relative_path=relative_path)
        fr.exists = exists
        # fr.full_clean()
        fr.save()

    return dataset


def iter_registered_directories(data_repository=None, tc=None, path=None):
    """Iterater over pairs (globus dir path, [list of files]) in any directory that
    contains session.metadat.json."""
    tc = tc or globus_transfer_client()
    # Default path: the root of the data repository.
    path = path or data_repository.path
    try:
        contents = tc.operation_ls(data_repository.globus_endpoint_id, path=path)
    except globus_sdk.exc.TransferAPIError as e:
        logger.warn(e)
        return
    contents = contents['DATA']
    subdirs = [file['name'] for file in contents if file['type'] == 'dir']
    files = [file['name'] for file in contents if file['type'] == 'file']
    # Yield the list of files if there is a session.metadata.json file.
    if 'session.metadata.json' in files:
        yield path, files
    # Recursively call the function in the subdirectories.
    for subdir in subdirs:
        subdir_path = op.join(path, subdir)
        yield from iter_registered_directories(
            tc=tc, data_repository=data_repository, path=subdir_path)


def update_file_exists(dataset):
    """Update the exists field if it is False and that it exists on Globus."""
    files = FileRecord.objects.filter(dataset=dataset)
    for file in files:
        file_exists_db = file.exists
        file_exists_globus = globus_file_exists(file)
        if file_exists_db and file_exists_globus:
            logger.info(
                "File %s exists on %s.", file.relative_path, file.data_repository.name)
        elif file_exists_db and not file_exists_globus:
            logger.warn(
                "File %s exists on %s in the database but not in globus.",
                file.relative_path, file.data_repository.name)
        elif not file_exists_db and file_exists_globus:
            logger.info(
                "File %s exists on %s, updating the database.",
                file.relative_path, file.data_repository.name)
            file.exists = True
            file.save()
        elif not file_exists_db and not file_exists_globus:
            logger.info(
                "File %s does not exist on %s.",
                file.relative_path, file.data_repository.name)


def transfers_required(dataset):
    """Iterate over the file transfers that need to be done."""

    # Choose a file record that exists and, if possible, is not stored on a Globus personal
    # endpoint.
    existing_file = FileRecord.objects.filter(
        dataset=dataset, exists=True, data_repository__globus_is_personal=False).first()
    if not existing_file:
        existing_file = FileRecord.objects.filter(
            dataset=dataset, exists=True).first()
    if not existing_file:
        logger.debug("No file exists on any data repository for dataset %s.", dataset.pk)
        return

    # Launch the file transfers for the missing files.
    missing_files = FileRecord.objects.filter(dataset=dataset, exists=False)
    for missing_file in missing_files:
            assert existing_file.exists
            assert not missing_file.exists
            # WARNING: we should check that the destination data_repository is not personal if
            # the source repository is personal.
            if (missing_file.data_repository.globus_is_personal and
                    existing_file.data_repository.globus_is_personal):
                logger.warn("Our globus subscription does not support file transfer between two "
                            "personal servers.")
                continue
            yield {
                'source_data_repository': existing_file.data_repository.name,
                'destination_data_repository': missing_file.data_repository.name,
                'source_path': _get_absolute_path(existing_file),
                'destination_path': _get_absolute_path(missing_file),
                'source_file_record': str(existing_file.pk),
                'destination_file_record': str(missing_file.pk),
            }
