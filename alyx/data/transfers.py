import json
import logging
import os
import os.path as op
import re

from django.db.models import Case, When, Count, Q
import globus_sdk
import numpy as np

from alyx import settings
from data.models import FileRecord, Dataset, DatasetType, DataFormat, DataRepository
from actions.models import Session

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
    # a dataset is incomplete if
    # -     there is no file on the flatiron Globus
    # and/or
    # -     none of globus personnal endpoints have a file
    q1 = Q(file_records__exists=False) & Q(file_records__data_repository__globus_is_personal=False)
    noremote = Dataset.objects.filter(q1)
    q2 = Q(file_records__exists=True) & Q(file_records__data_repository__globus_is_personal=True)
    nolocal = Dataset.objects.annotate(numok=Count(Case(When(q2, then=1)))).filter(numok=0)
    return nolocal.values_list('id').union(noremote.values_list('id')).distinct()
#    return FileRecord.objects.filter(exists=False).values_list('dataset', flat=True).distinct()


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
        label=label[0: min(len(label), 128)],
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
        logger.warning(e)
        return False
    for existing_file in existing:
        if existing_file['name'] in (name, name_uuid) and existing_file['size'] > 0:
            return True
    return False


def _filename_matches_pattern(filename, pattern):
    filename = op.basename(filename)
    reg = pattern.replace('.', r'\.').replace('_', r'\_').replace('*', r'.*')
    return re.match(reg, filename, re.IGNORECASE)


def get_dataset_type(filename, qs=None):
    dataset_types = []
    qs = qs or DatasetType.objects.filter(filename_pattern__isnull=False)
    for dt in qs:
        if not dt.filename_pattern.strip():
            continue
        if _filename_matches_pattern(filename, dt.filename_pattern):
            dataset_types.append(dt)
    n = len(dataset_types)
    if n == 0:
        raise ValueError("No dataset type found for filename `%s`" % filename)
    elif n >= 2:
        raise ValueError("Multiple matching dataset types found for filename `%s`: %s" % (
            filename, ', '.join(map(str, dataset_types))))
    return dataset_types[0]


def get_data_format(filename):
    file_extension = op.splitext(filename)[-1]
    # This raises an error if there is 0 or 2+ matching data formats.
    return DataFormat.objects.get(file_extension=file_extension)


def _get_repositories_for_labs(labs):
    # List of data repositories associated to the subject's labs.
    repositories = set()
    for lab in labs:
        repositories.update(lab.repositories.all())
    return list(repositories)


def _create_dataset_file_records(
        rel_dir_path=None, filename=None, session=None, user=None,
        repositories=None, exists_in=None, collection=None):

    assert session is not None

    relative_path = op.join(rel_dir_path, filename)
    dataset_type = get_dataset_type(filename)
    data_format = get_data_format(filename)
    assert dataset_type
    assert data_format

    # Create the dataset.
    dataset, _ = Dataset.objects.get_or_create(
        collection=collection, name=filename, session=session,
        dataset_type=dataset_type, data_format=data_format)
    # The user doesn't have to be the same when getting an existing dataset, but we still
    # have to set the created_by field.
    dataset.created_by = user
    # Validate the fields.
    dataset.full_clean()
    dataset.save()

    # Create one file record per repository.
    exists_in = exists_in or ()
    for repo in repositories:
        exists = repo in exists_in
        # Do not create a new file record if it already exists.
        fr, _ = FileRecord.objects.get_or_create(
            dataset=dataset, data_repository=repo, relative_path=relative_path)
        fr.exists = exists
        # Validate the fields.
        fr.full_clean()
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
        logger.warning(e)
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
            logger.warning(
                "File %s exists on %s in the database but not in globus.",
                file.relative_path, file.data_repository.name)
            file.exists = False
            file.save()
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
                continue
            yield {
                'source_data_repository': existing_file.data_repository.name,
                'destination_data_repository': missing_file.data_repository.name,
                'source_path': _get_absolute_path(existing_file),
                'destination_path': _get_absolute_path(missing_file),
                'source_file_record': str(existing_file.pk),
                'destination_file_record': str(missing_file.pk),
            }


def bulk_sync(dry_run=False, lab=None):
    """
    updates the Alyx database file records field 'exists' by looking at each Globus repository.
    Only the files belonging to a dataset for which one main repository as a missing file are
    checked on the Globus endpoints (a main repository is a repository with the
    globus_is_personnal field set to False). Also fills dataset size if non-existent.
    This is meant to be launched before the transfer() function
    """
    dfs = FileRecord.objects.filter(exists=False, data_repository__globus_is_personal=False)
    if lab:
        dfs = dfs.filter(data_repository__lab__name=lab)
    # get all the datasets concerned and then back down to get all files for all those datasets
    dsets = Dataset.objects.filter(pk__in=dfs.values_list('dataset').distinct())
    all_files = FileRecord.objects.filter(pk__in=dsets.values('file_records')).order_by(
        'dataset__created_datetime')
    if dry_run:
        fvals = all_files.values_list('relative_path', flat=True).distinct()
        for l in list(fvals):
            print(l)
        return fvals

    gc = globus_transfer_client()
    # loop over all files concerned by a transfer and update the exists and filesize fields
    files_to_ls = all_files.order_by('data_repository__globus_endpoint_id', 'relative_path')
    _last_ep = None
    _last_path = None
    nfiles = files_to_ls.count()
    c = 0
    for qf in files_to_ls:
        c += 1
        # if the last endpoint has already been queried, do not repeat the query
        if _last_ep != qf.data_repository.globus_endpoint_id:
            _last_ep = qf.data_repository.globus_endpoint_id
            ep_info = gc.get_endpoint(_last_ep)
        # if the endpoint is not connected skip
        # NB: the non-personal endpoints have a None so need to explicitly test for False
        if ep_info['gcp_connected'] is False:
            logger.warning('UNREACHABLE Endpoint "' + ep_info['display_name'] +
                           '" (' + str(_last_ep) + ') ' + qf.relative_path)
            continue
        # if we already listed the current path of the endpoint, do not repeat the rest ls command
        cpath, fil = os.path.split(qf.relative_path)
        fil_uuid = _add_uuid_to_filename(fil, qf.dataset_id)
        cpath = qf.data_repository.globus_path + cpath
        if _last_path != cpath:
            _last_path = cpath
            try:
                logger.info(str(c) + '/' + str(nfiles) + ' ls ' + cpath + ' on ' + str(_last_ep))
                ls_result = gc.operation_ls(_last_ep, path=_last_path)
            except globus_sdk.exc.TransferAPIError:
                ls_result = []
        # compare the current file against the ls list, update the file_size if necessary
        exists = False
        for ind, gfil in enumerate(ls_result):
            if gfil['name'] in (fil_uuid, fil):
                exists = True
                if qf.dataset.file_size != gfil['size']:
                    qf.dataset.file_size = gfil['size']
                    qf.dataset.save()
                break
        # update the filerecord exists field if needed
        if qf.exists != exists:
            qf.exists = exists
            qf.save()
            logger.info(str(c) + '/' + str(nfiles) + ' ' + str(qf.data_repository.name) + ':' +
                        qf.relative_path + ' exist set to ' + str(exists) + ' in Alyx')


def _filename_from_file_record(fr, add_uuid=False):
    fn = fr.data_repository.globus_path + fr.relative_path
    if add_uuid:
        fn = _add_uuid_to_filename(fn, fr.dataset.pk)
    return fn


def bulk_transfer(dry_run=False, lab=None):
    """
    uploads files from a local Globus repository to a main repository if the file on the main
    repository does not exist.
    should be launched after bulk_sync() function
    """
    gc = globus_transfer_client()
    dfs = FileRecord.objects.filter(exists=False, data_repository__globus_is_personal=False)
    if lab:
        dfs = dfs.filter(data_repository__lab__name=lab)
    dfs = dfs.order_by('data_repository__globus_endpoint_id', 'relative_path')
    pri_repos = DataRepository.objects.filter(globus_is_personal=False)
    sec_repos = DataRepository.objects.filter(globus_is_personal=True)
    tm = np.zeros([pri_repos.count(), sec_repos.count()], dtype=object)
    nfiles = dfs.count()
    c = 0
    # create the tasks
    for ds in dfs:
        c += 1
        ipri = [ind for ind, cr in enumerate(pri_repos) if cr == ds.data_repository][0]
        src_file = ds.dataset.file_records.filter(exists=True).first()
        if not src_file:
            logger.warning(str(ds.data_repository.name) + ':' + ds.relative_path +
                           ' is nowhere to ' + 'be found in local AND remote repositories')
            continue
        isec = [ind for ind, cr in enumerate(sec_repos) if cr == src_file.data_repository][0]
        # if the transfer doesn't exist, create it:
        if tm[ipri][isec] == 0:
            label = sec_repos[isec].name + ' to ' + pri_repos[ipri].name
            tm[ipri][isec] = globus_sdk.TransferData(
                gc,
                source_endpoint=sec_repos[isec].globus_endpoint_id,
                destination_endpoint=pri_repos[ipri].globus_endpoint_id,
                verify_checksum=True,
                sync_level='checksum',
                label=label)
        # add the transfer to the current task
        destination_file = _filename_from_file_record(ds, add_uuid=True)
        source_file = _filename_from_file_record(src_file)
        tm[ipri][isec].add_item(source_path=source_file, destination_path=destination_file)
        logger.info(str(c) + '/' + str(nfiles) + ' ' + source_file + ' to ' + destination_file)
    # launch the transfer tasks
    if dry_run:
        return
    for t in tm.flatten():
        if t == 0:
            continue
        gc.submit_transfer(t)


def _get_session(subject=None, date=None, number=None, user=None):
    # https://github.com/cortex-lab/alyx/issues/408
    if not subject or not date:
        return None
    # If a base session for that subject and date already exists, use it;
    base = Session.objects.filter(
        subject=subject, start_time__date=date, parent_session__isnull=True).first()
    # Ensure a base session for that subject and date exists.
    if not base:
        raise ValueError("A base session for %s on %s does not exist" % (subject, date))
    if user and user not in base.users.all():
        base.users.add(user.pk)
        base.save()
    # If a subsession for that subject, date, and expNum already exists, use it;
    session = Session.objects.filter(
        subject=subject, start_time__date=date, number=number).first()
    # Ensure the subsession exists.
    if not session:
        raise ValueError("A session for %s/%d on %s does not exist" % (subject, number, date))
    if user and user not in session.users.all():
        session.users.add(user.pk)
        session.save()
    # Attach the subsession to the base session if not already attached.
    if (not session.parent_session) and base != session:
        session.parent_session = base
        session.save()
    return session
