import json
import structlog
import os
import os.path as op
import re
import time
from pathlib import Path
from fnmatch import fnmatch

from django.db.models import Case, When, Count, Q, F
import globus_sdk
import numpy as np
from one.alf.files import filename_parts, add_uuid_string
from one.alf.spec import is_valid

from alyx import settings
from data.models import FileRecord, Dataset, DatasetType, DataFormat, DataRepository
from rest_framework.response import Response
from actions.models import Session

logger = structlog.get_logger(__name__)

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
    destination_path = add_uuid_string(destination_path, source_fr.dataset.pk).as_posix()

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
    name_uuid = add_uuid_string(name, file_record.dataset.pk).as_posix()
    try:
        existing = tc.operation_ls(file_record.data_repository.globus_endpoint_id, path=dir_path)
    except globus_sdk.TransferAPIError as e:
        logger.warning(e)
        return False
    for existing_file in existing:
        if existing_file['name'] in (name, name_uuid) and existing_file['size'] > 0:
            return True
    return False


def get_dataset_type(filename, qs=None):
    """Get the dataset type from a given filename"""
    dataset_types = []
    for dt in qs or DatasetType.objects.all():
        if not dt.filename_pattern.strip():
            # If the filename pattern is null, check whether the filename object.attribute matches
            # the dataset type name.
            if is_valid(filename):
                obj_attr = '.'.join(filename_parts(filename)[1:3])
            else:  # will match name against filename sans extension
                obj_attr = op.splitext(filename)[0]
            if dt.name == obj_attr:
                dataset_types.append(dt)
        # Check whether pattern matches filename
        elif fnmatch(op.basename(filename).lower(), dt.filename_pattern.lower()):
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


def _get_repositories_for_labs(labs, server_only=False):
    # List of data repositories associated to the subject's labs.
    repositories = set()
    for lab in labs:
        if server_only:
            repos = lab.repositories.filter(globus_is_personal=False)
        else:
            repos = lab.repositories.all()
        repositories.update(repos)
    return list(repositories)


def _get_name_collection_revision(file, rel_dir_path, subject, date):

    # Get collections/revisions for each file
    fullpath = Path(rel_dir_path).joinpath(file).as_posix()
    # Index of relative path (stuff after session path)
    i = re.search(f'{subject}/{date}/' + r'\d{1,3}', fullpath).end()
    subdirs = list(Path(fullpath[i:].strip('/')).parent.parts)
    # Check for revisions (folders beginning and ending with '#')
    # Fringe cases:
    #   '#' is a collection
    #   '##' is an empty revision
    #   '##blah#5#' is a revision named '#blah#5'
    is_rev = [len(x) >= 2 and x[0] + x[-1] == '##' for x in subdirs]
    if any(is_rev):
        # There may be only 1 revision and it cannot contain sub folders
        if is_rev.index(True) != len(is_rev) - 1:
            data = {'status_code': 400,
                    'detail': 'Revision folders cannot contain sub folders'}
            return None, Response(data=data, status=400)
        revision = subdirs.pop()[1:-1]
    else:
        revision = None

    info = dict()
    info['full_path'] = fullpath
    info['filename'] = Path(file).name
    info['collection'] = '/'.join(subdirs)
    info['revision'] = revision
    info['rel_dir_path'] = fullpath[:i]

    return info, None


def _change_default_dataset(session, collection, filename):
    dataset = Dataset.objects.filter(session=session, collection=collection, name=filename,
                                     default_dataset=True)
    if dataset.count() > 0:
        dataset.update(default_dataset=False)


def _check_dataset_protected(session, collection, filename):
    # Order datasets by the latest revision with the original one last
    dataset = Dataset.objects.filter(session=session, collection=collection,
                                     name=filename).order_by(
        F('revision__created_datetime').desc(nulls_last=True))
    if dataset.count() == 0:
        return False, []
    else:
        protected = any([d.is_protected for d in dataset])
        protected_info = [{d.revision.name if d.revision else '': d.is_protected}
                          for d in dataset]
        return protected, protected_info


def _create_dataset_file_records(
        rel_dir_path=None, filename=None, session=None, user=None,
        repositories=None, exists_in=None, collection=None, hash=None,
        file_size=None, version=None, revision=None, default=None):

    assert session is not None
    revision_name = f'#{revision.name}#' if revision else ''
    relative_path = op.join(rel_dir_path, collection or '', revision_name, filename)
    dataset_type = get_dataset_type(filename)
    data_format = get_data_format(filename)
    assert dataset_type
    assert data_format

    # If we are going to set this one as the default we need to change any previous ones with
    # same session, collection and name to have default flag to false
    if default:
        _change_default_dataset(session, collection, filename)

    # Get or create the dataset.
    dataset, is_new = Dataset.objects.get_or_create(
        collection=collection, name=filename, session=session,
        dataset_type=dataset_type, data_format=data_format, revision=revision)
    dataset.default_dataset = default is True
    dataset.save()

    # If the dataset already existed see if it is protected (i.e can't be overwritten)
    if not is_new:
        protected_tag = dataset.tags.filter(protected=True).count()
        if protected_tag > 0:
            # Raise an error indicating dataset cannot be overwritten
            data = {'status_code': 403,
                    'detail': 'Dataset ' + str(dataset.pk) + ' is protected, cannot patch'}
            return None, Response(data=data, status=403)

    # The user doesn't have to be the same when getting an existing dataset, but we still
    # have to set the created_by field.
    dataset.created_by = user
    if version is not None:
        dataset.version = version
    """
    if a hash/filesize is provided, label the dataset with it
    if there was a hash and or filesize in the dataset and the provided items are different,
    then set the existing file records exists field to False
    If the hash doesn't exist and/or can't be verified, assume that the dataset is patched
    """
    is_patched = True
    if hash is not None:
        if dataset.hash is not None:
            is_patched = not dataset.hash == hash
        dataset.hash = hash
    if file_size is not None:
        dataset.file_size = file_size
    # Validate the fields.
    dataset.full_clean()
    dataset.save()

    # Create one file record per repository.
    exists_in = exists_in or ()
    for repo in repositories:
        exists = repo in exists_in
        # Do not create a new file record if it already exists.
        fr, is_new = FileRecord.objects.get_or_create(
            dataset=dataset, data_repository=repo, relative_path=relative_path)
        if is_new or is_patched:
            fr.exists = exists
            fr.json = None  # this is important if a dataset is patched during an ongoing transfer
        # Validate the fields.
        fr.full_clean()
        fr.save()

    return dataset, None


def iter_registered_directories(data_repository=None, tc=None, path=None):
    """Iterater over pairs (globus dir path, [list of files]) in any directory that
    contains session.metadat.json."""
    tc = tc or globus_transfer_client()
    # Default path: the root of the data repository.
    path = path or data_repository.path
    try:
        contents = tc.operation_ls(data_repository.globus_endpoint_id, path=path)
    except globus_sdk.TransferAPIError as e:
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


def bulk_sync(dry_run=False, lab=None, gc=None, check_mismatch=False):
    """
    updates the Alyx database file records field 'exists' by looking at each Globus repository.
    This is meant to be launched before the transfer() function
    Local filerecord =  data_repository__globus_is_personal=True
    Server filerecord =  data_repository__globus_is_personal=False
    The algorithm looks at datasets for which the server data file does not exist. For each
        -   the locals filerecords are checked and their exist flag updated
        -   the server filerecords that have a json__transfer_pending=True flag are checked and
    their exist flags updated
    :param dry_run (False) just prints the files if True
    :param lab (optional) specific lab name only
    :param gc (optional) globus transfer client. If not given will instantiated within fucntion
    :param local_only: (False) if set to True, only local files will be checked. This is useful
    :param check_mismatch: (False) if set to True, will add to the queries filerecords existing
     on SDSC but labeled as mismatched hash
    for patching files
    """
    if check_mismatch:
        dfs = FileRecord.objects.filter(
            Q(exists=False, data_repository__globus_is_personal=False,
              data_repository__name__icontains='flatiron') |
            Q(json__has_key="mismatch_hash"))
    else:
        dfs = FileRecord.objects.filter(
            Q(exists=False, data_repository__globus_is_personal=False,
              data_repository__name__icontains='flatiron'))
    if lab:
        dfs = dfs.filter(data_repository__lab__name=lab)
    # get all the datasets concerned and then back down to get all files for all those datasets
    dsets = Dataset.objects.filter(pk__in=dfs.values_list('dataset').distinct())
    all_files = FileRecord.objects.filter(
        dataset__in=dsets).order_by('-dataset__created_datetime')
    # checks all local files by default, and only transfer pending files for the server
    all_files = all_files.filter(
        Q(data_repository__globus_is_personal=True) |
        Q(json__has_key="transfer_pending"))
    if dry_run:
        fvals = all_files.values_list('relative_path', flat=True).distinct()
        for fval in list(fvals):
            print(fval)
        return fvals

    gc = gc or globus_transfer_client()
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
        fil_uuid = add_uuid_string(fil, qf.dataset_id).as_posix()
        cpath = qf.data_repository.globus_path + cpath
        if _last_path != cpath:
            _last_path = cpath
            try:
                print(str(c) + '/' + str(nfiles) + ' ls ' + cpath + ' on ' + str(_last_ep))
                ls_result = gc.operation_ls(_last_ep, path=_last_path)
            except globus_sdk.TransferAPIError:
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
            # sets the json field to None so that the transfer pending flag is nulled
            if exists:
                qf.dataset.file_records.update(json=None)
            print(str(c) + '/' + str(nfiles) + ' ' + str(qf.data_repository.name) + ':' +
                  qf.relative_path + ' exist set to ' + str(exists) + ' in Alyx')


def _filename_from_file_record(fr, add_uuid=False):
    fn = fr.data_repository.globus_path + fr.relative_path
    if add_uuid:
        fn = add_uuid_string(fn, fr.dataset.pk).as_posix()
    return fn


def bulk_transfer(dry_run=False, lab=None, gc=None):
    """
    uploads files from a local Globus repository to a main repository if the file on the main
    repository does not exist.
    should be launched after bulk_sync() functions
    """
    # splits the jobs in one for small files and another for big files so that big raw
    # ephys files don't hold the transfer of small behaviour/training files
    _bulk_transfer(dry_run=dry_run, lab=lab, maxsize=1024 ** 3, gc=gc)
    _bulk_transfer(dry_run=dry_run, lab=lab, minsize=1024 ** 3, gc=gc)


def _bulk_transfer(dry_run=False, lab=None, maxsize=None, minsize=None, gc=None):
    """
    Transfer in bulk data to Flat Iron. 2 transfers are created according to file-size so that
    smaller files get in earlier. The query of data/.FileRecord records to transfer is based
    on the exists flag (True) and the globus personal (False).
    :param dry_run: (bool)
    :param lab: (str) lab name: only transfer files from this lab
    :param maxsize: (int) maximum file size for transfer (allows to split small and big transfers)
    :param minsize: (int) minimum file size for transfer (see above)
    :param gc (optional) globus transfer client.
    :return: globus_client, transfer_matrix (an array of transfer objects)
    """
    dfs = FileRecord.objects.filter(
        (Q(exists=False, data_repository__globus_is_personal=False,
           data_repository__name__icontains='flatiron') |
         Q(json__has_key="mismatch_hash")) &
        ~Q(json__has_key="transfer_pending")
    )
    if minsize:
        dfs = dfs.filter(dataset__file_size__gt=minsize)
    if maxsize:
        dfs = dfs.exclude(dataset__file_size__gt=maxsize)
    if not dfs:
        return
    if lab:
        dfs = dfs.filter(data_repository__lab__name=lab)
    gc, tm = _globus_transfer_filerecords(dfs, dry=dry_run, gc=gc)
    return gc, tm


def _globus_transfer_filerecords(dfs, dry=True, gc=None):
    """
    Transfers the file records. The query set has to contain only is_globus_personal=False flag
    (ie. they are server side file records). The algorithm creates a transfer object for each
    unique pair of globus source / globus destination ids and launches the transfers at the end.
    :param dfs: file records queryset
    :param dry:
    :param gc (optional) globus transfer client. If not given will instantiated within function
    :return: globus_client, transfer_matrix (an array of transfer objects)
    """
    gc = None if dry else gc or globus_transfer_client()
    dfs = dfs.order_by('data_repository__globus_endpoint_id', 'relative_path')
    pri_repos = DataRepository.objects.filter(globus_is_personal=False, name__icontains='flatiron')
    sec_repos = DataRepository.objects.filter(globus_is_personal=True)
    tm = np.zeros([pri_repos.count(), sec_repos.count()], dtype=object)
    nfiles = dfs.count()
    c = 0
    # create the tasks
    for ds in dfs:
        c += 1
        ipri = [ind for ind, cr in enumerate(pri_repos) if cr == ds.data_repository][0]
        src_file = ds.dataset.file_records.filter(~Q(data_repository__name__icontains='aws'),
                                                  exists=True).first()
        if not src_file:
            logger.warning(str(ds.data_repository.name) + ':' + ds.relative_path +
                           ' is nowhere to ' + 'be found in local AND remote repositories')
            ds.json = {'local_missing': True}
            ds.save()
            continue
        isec = next((ind for ind, cr in enumerate(sec_repos) if cr == src_file.data_repository),
                    None)
        if isec is None:
            print("no _isec")
            continue
        # if the transfer doesn't exist, create it:
        if tm[ipri][isec] == 0:
            label = sec_repos[isec].name + ' to ' + pri_repos[ipri].name
            if not dry:
                tm[ipri][isec] = globus_sdk.TransferData(
                    gc,
                    source_endpoint=sec_repos[isec].globus_endpoint_id,
                    destination_endpoint=pri_repos[ipri].globus_endpoint_id,
                    verify_checksum=True,
                    sync_level='checksum',
                    label=label)
            # If dry make a fake transfer client dict
            else:
                tm[ipri][isec] = {'source_endpoint': sec_repos[isec].globus_endpoint_id,
                                  'destination_endpoint': pri_repos[ipri].globus_endpoint_id,
                                  'label': label,
                                  'DATA': []}

        # add the transfer to the current task
        destination_file = _filename_from_file_record(ds, add_uuid=True)
        source_file = _filename_from_file_record(src_file)
        if not dry:
            tm[ipri][isec].add_item(source_path=source_file, destination_path=destination_file)
        else:
            tm[ipri][isec]['DATA'].append({'source_path': source_file,
                                           'destination_path': destination_file})

        print(str(c) + '/' + str(nfiles) + ' ' + source_file + ' to ' + destination_file)
    # launch the transfer tasks
    if dry:
        return None, tm
    for t in tm.flatten():
        if t == 0:
            continue
        gc.submit_transfer(t)
    dfs.exclude(json__has_key="local_missing").update(json={'transfer_pending': True})
    return gc, tm


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


def globus_transfer_datasets(dsets, dry=True):
    """
    :param dsets: Dataset queryset
    :param dry:
    :return: globus_client, transfer_matrix (an array of transfer objects)
    """
    frecs = FileRecord.objects.filter(data_repository__globus_is_personal=False, dataset__in=dsets)
    gc, tm = _globus_transfer_filerecords(frecs, dry=dry)
    return gc, tm


def globus_delete_local_datasets(datasets, dry=True, gc=None):
    """
    For each dataset in the queryset delete the file records belonging to a Globus personal repo
    only if a server file exists and matches the size.
    :param datasets:
    :param dry: default True
    :return:
    """
    # first get the list of Globus endpoints concerned
    file_records = FileRecord.objects.filter(dataset__in=datasets)
    globus_endpoints = file_records.values_list('data_repository__globus_endpoint_id',
                                                flat=True).distinct()
    # create a globus delete_client for each globus endpoint
    gtc = gc or globus_transfer_client()
    delete_clients = []
    for ge in globus_endpoints:
        delete_clients.append(globus_sdk.DeleteData(gtc, ge, label=''))

    def _ls_globus(file_record, add_uuid=False):
        N_RETRIES = 3
        for ntry in range(3):
            try:
                path = Path(_filename_from_file_record(file_record, add_uuid=add_uuid))
                ls_obj = gtc.operation_ls(file_record.data_repository.globus_endpoint_id,
                                          path=path.parent)
            except globus_sdk.TransferAPIError as err:
                logger.warning('Globus error trial %i/%i', ntry + 1, N_RETRIES, exc_info=err)
                if 'ClientError.NotFound' in str(err):
                    return
                elif ntry == N_RETRIES - 1:
                    raise
                time.sleep(2)
                continue
            break
        return [ls for ls in ls_obj['DATA'] if ls['name'] == path.name]
    # appends each file for deletion
    fr2delete = []
    del_client = []
    for ds in datasets:
        # check the existence of the server file
        fr_server = ds.file_records.filter(exists=True,
                                           data_repository__globus_is_personal=False,
                                           data_repository__name__icontains='flatiron').first()
        if fr_server is None:
            logger.warning(str(ds.session) + '/' + ds.collection +
                           '/' + ds.name + " doesnt exist on server - skipping")
            continue
        ls_server = _ls_globus(fr_server, add_uuid=True)
        # if the file is not found on the remote server, do nothing
        if ls_server == [] or ls_server is None:
            logger.warning(fr_server.relative_path + " not found on server - skipping,")
            continue
        fr_local = ds.file_records.filter(data_repository__globus_is_personal=True)
        for frloc in fr_local:
            ls_local = _ls_globus(frloc)
            # if the data is not found on the local server, remove the file record from database
            if ls_local == [] or ls_local is None:
                logger.info('NO FILE ON LOCAL, SKIP: ' + _filename_from_file_record(frloc))
                fr2delete.append(frloc.id)
                continue
            # if the file sizes don't match throw a warning and continue
            if not ls_local[0]['size'] == ls_server[0]['size']:
                logger.warning(frloc.relative_path + " sizes don't check out, skipping")
                continue
            # the files exist local and remote,
            fr2delete.append(frloc.id)
            file2del = _filename_from_file_record(frloc)
            del_client = [dc for dc in delete_clients if dc['endpoint'] ==
                          str(frloc.data_repository.globus_endpoint_id)][0]
            del_client.add_item(file2del)
            logger.info('DELETE: ' + _filename_from_file_record(frloc))
    # launch the deletion jobs and remove records from the database
    if dry:
        return del_client
    for dc in delete_clients:
        # submitting a deletion without data will create an error
        if dc['DATA'] == []:
            continue
        gtc.submit_delete(dc)
    # remove file records
    frecs = FileRecord.objects.filter(id__in=fr2delete).exclude(
        data_repository__globus_is_personal=False)
    frecs.delete()


def globus_delete_datasets(datasets, dry=True, local_only=False, gc=None):
    """
    For each dataset in the queryset, delete the dataset record in the database and attempt
    a Globus delete for all physical file-records associated.
    Admin territory.
    :param datasets:
    :param dry: default True
    :param local_only: only delete from non-FlatIron locations: in this case only file records will
    be removed from the database, not the datasets records.
    :param gc: globus_transfer_client
    :return:
    """
    # first get the list of Globus endpoints concerned
    file_records = FileRecord.objects.filter(~Q(data_repository__name__icontains='aws'),
                                             dataset__in=datasets)
    if local_only:
        file_records = file_records.filter(data_repository__globus_is_personal=True)
        file_records = file_records.exclude(data_repository__name__icontains='flatiron')
    file2del = globus_delete_file_records(file_records, dry=dry, gc=gc)

    if dry or local_only:
        return file2del

    for ds in datasets:
        ds.delete()


def globus_delete_file_records(file_records, dry=True, gc=None):
    """
    For each filecord in the queryset, attempt a Globus delete for all physical file-records
    associated. Admin territory.
    :param file_records:
    :param dry: default True
    :param gc (optional) globus transfer client. If not given will be instantiated within function
    :return:
    """
    # first get the list of Globus endpoints concerned
    globus_endpoints = file_records.values_list(
        'data_repository__globus_endpoint_id', flat=True).distinct()
    related_datasets = file_records.values_list('dataset', flat=True).distinct()

    # create a globus delete_client for each globus endpoint
    gtc = gc or globus_transfer_client()
    delete_clients = []
    if not dry:
        # delete_clients = []
        for ge in globus_endpoints:
            delete_clients.append(globus_sdk.DeleteData(gtc, ge, label=''))
    # appends each file for deletion
    for i, ge in enumerate(globus_endpoints):
        current_path = None
        # get endpoint status before continuing
        endpoint_info = gtc.get_endpoint(ge)
        # if the endpoint is not globus_connect (ie. not personal) this returns None
        endpoint_connected = endpoint_info.data['gcp_connected'] is not False
        # if the endpoint is offline skip
        if not endpoint_connected:
            logger.warning(endpoint_info.data['display_name'] + 'is offline. SKIPPING.')
            continue
        frs = FileRecord.objects.filter(
            ~Q(data_repository__name__icontains='aws'),
            dataset__in=related_datasets,
            data_repository__globus_endpoint_id=ge).order_by('relative_path')
        logger.info(str(frs.count()) + ' files to delete on ' + endpoint_info.data['display_name'])
        for fr in frs:
            add_uuid = not fr.data_repository.globus_is_personal
            file2del = _filename_from_file_record(fr, add_uuid=add_uuid)
            if dry:
                delete_clients.append(file2del)
                logger.warning(file2del)
            else:
                if current_path != Path(file2del).parent:
                    current_path = Path(file2del).parent
                    try:
                        ls_current_path = [f['name'] for f in
                                           gtc.operation_ls(ge, path=current_path)]
                    except globus_sdk.TransferAPIError as err:
                        if 'ClientError.NotFound' in str(err):
                            logger.warning('DIR NOT FOUND: ' + file2del + ' on ' +
                                           str(fr.data_repository.name))
                            ls_current_path = []
                        else:
                            raise err
                if Path(file2del).name in ls_current_path:
                    logger.warning(
                        'DELETE: ' + file2del + ' on ' + str(fr.data_repository.name))
                    delete_clients[i].add_item(file2del)
                else:
                    logger.warning(
                        'FILE NOT FOUND: ' + file2del + ' on ' + str(fr.data_repository.name))
    # launch the deletion jobs and remove records from the database
    if dry:
        return delete_clients
    # launch the deletion jobs and remove records from the database
    for dc in delete_clients:
        # submitting a deletion without data will create an error
        if dc['DATA'] == []:
            logger.warning('SUBMIT DELETE SKIPPED AS NO DATA: ' + str(dc))
            continue
        logger.warning('SUBMIT DELETE: ' + str(dc))
        gtc.submit_delete(dc)
    # ideally here we would make some synchronous process and some error handling
    file_records.delete()

    return
