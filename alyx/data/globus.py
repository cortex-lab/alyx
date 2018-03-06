import json
import logging
import os
import os.path as op
import re

import globus_sdk

from alyx import settings
from data.models import FileRecord

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
    return op.join(file_record.data_repository.path,
                   file_record.relative_path)


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
    path = op.dirname(_get_absolute_path(file_record))
    name = op.basename(file_record.relative_path)
    name = _add_uuid_to_filename(name, file_record.dataset.pk)
    try:
        existing = tc.operation_ls(file_record.data_repository.globus_endpoint_id, path=path)
    except globus_sdk.exc.TransferAPIError as e:
        logger.warn(e)
        return False
    for existing_file in existing:
        if existing_file['name'] == name and existing_file['size'] > 0:
            return True
    return False


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
        logger.warn("No file exists on any data repository for dataset %s.", dataset.pk)
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
