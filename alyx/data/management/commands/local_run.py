from misc.models import Lab, LabLocation, LabMember
from data.models import DataRepository, DataRepositoryType, FileRecord, Revision, Dataset
from data.transfers import (bulk_sync, _bulk_transfer, globus_delete_local_datasets,
                            globus_delete_datasets)
from subjects.models import Subject
from actions.models import Session
from django.urls import reverse
from django.test import Client

import os
import numpy as np
from pathlib import Path
import json
import globus_sdk as globus

from alyx.settings_lab import GLOBUS_CLIENT_ID
# TODO some way to get the hostname automatically
SERVER_NAME = 'localhost:8000'


def globus_login(globus_client_id):
    # This assumes globus stuff has been setup using ibllib.io.globus. Ideally need to make globus
    # functions in data.transfers flexible so it can deal with either alyx or ibllib way!
    token_path = Path.home().joinpath('.globus', '.admin')
    with open(token_path, 'r') as f:
        token = json.load(f)
    client = globus.NativeAppAuthClient(globus_client_id)
    client.oauth2_start_flow(refresh_tokens=True)
    authorizer = globus.RefreshTokenAuthorizer(token['refresh_token'], client)

    return globus.TransferClient(authorizer=authorizer)


def get_local_endpoint():
    """
    Get the local endpoint id of the computer
    :return:
    """
    id_path = Path.home().joinpath(".globusonline", "lta")
    with open(id_path.joinpath("client-id.txt"), 'r') as fid:
        globus_id = fid.read()
    return globus_id.strip()


def get_local_globus_path():
    config_path = Path.home().joinpath(".globusonline", "lta")
    message = 'Please make a config-paths file in ./globus/lta that has the contains the ' \
              'folder on your local endpoint accessible by globus e.g echo "/mnt/s0/Data" > ' \
              '~/.globusonline/lta/config-paths'
    assert(config_path.joinpath("config-paths").exists()), message
    with open(config_path.joinpath("config-paths"), 'r') as fid:
        globus_path = fid.read()

    return globus_path.strip().split(',')[0]


def get_local_path(local_globus_path):
    if os.environ.get('WSL_DISTRO_NAME', None):
        local_path = str(Path('/mnt/c/').joinpath(*local_globus_path.split('/')[2:])) + '/'
    else:
        local_path = local_globus_path
    return local_path


def client_login(client):
    one_path = Path.home().joinpath('.one_params')
    with open(one_path, 'r') as f:
        one = json.load(f)

    client.login(username=one['ALYX_LOGIN'], password=one['ALYX_PWD'])

    return client


def setup():

    # Make sure we can log in
    gtc = globus_login(GLOBUS_CLIENT_ID)
    assert(gtc)

    # Check that the local endpoint is connected
    local_endpoint_id = get_local_endpoint()
    endpoint_info = gtc.get_endpoint(local_endpoint_id)
    assert(endpoint_info['gcp_connected'])

    # Check that the flatiron endpoint is connected
    flatiron_endpoint_id = (DataRepository.objects.filter(globus_is_personal=False).
                            first().globus_endpoint_id)
    endpoint_info = gtc.get_endpoint(flatiron_endpoint_id)
    assert(endpoint_info['gcp_connected'] is not False)

    # Make sure we have the correct accessible local globus path
    local_globus_path = get_local_globus_path()
    assert(gtc.operation_ls(local_endpoint_id, path=local_globus_path))

    # Connect to client and check we can log in properly
    client = Client()
    client = client_login(client)
    r = client.get(path='/', SERVER_NAME=SERVER_NAME)
    assert(r.status_code == 200)

    # Create a test lab
    lab_name = 'testlab'
    lab, _ = Lab.objects.get_or_create(name=f'{lab_name}')

    # Create a lab location in test lab
    lab_location, _ = LabLocation.objects.get_or_create(name=f'{lab_name}_location', lab=lab)

    # Create a testlab user
    username = f'{lab_name}_user'
    user, _ = LabMember.objects.get_or_create(username=username)

    # Create data repositories for the test lab
    # 1. For flatiron
    repo_type = DataRepositoryType.objects.get(name='Fileserver')
    name = f'flatiron_{lab_name}'
    hostname = 'ibl.flatironinstitute.org'
    data_url = f'https://ibl.flatironinstitute.org/{lab_name}/Subjects/'
    flatiron_globus_path = f'/{lab_name}/Subjects/'
    globus_is_personal = False
    flatiron_data_repo, _ = DataRepository.\
        objects.get_or_create(name=name, repository_type=repo_type, hostname=hostname,
                              data_url=data_url, globus_path=flatiron_globus_path,
                              globus_endpoint_id=flatiron_endpoint_id,
                              globus_is_personal=globus_is_personal)

    # 2. For local server
    name = f'{lab_name}_SR'
    globus_is_personal = True
    local_globus_path = str(Path(local_globus_path).joinpath(lab_name, 'Subjects')) + '/'
    local_data_repo, _ = DataRepository.\
        objects.get_or_create(name=name, repository_type=repo_type, globus_path=local_globus_path,
                              globus_endpoint_id=local_endpoint_id,
                              globus_is_personal=globus_is_personal)

    # Add the data repos to the lab
    lab.repositories.add(flatiron_data_repo)
    lab.repositories.add(local_data_repo)
    lab.save()

    # Now make a subject matched to the lab
    nickname = f'{lab_name}_001'
    subject, _ = Subject.objects.get_or_create(nickname=nickname, lab=lab, responsible_user=user)

    # And a session associated with the subject
    session, _ = Session.objects.get_or_create(subject=subject, location=lab_location, lab=lab,
                                               start_time='2021-03-03', number=1)

    # Make a revision object for revision testing
    revision = Revision.objects.get_or_create(name='version_testing', collection='version_testing')

    """
    TEST TRANSFER OF DATA WITH NO REVISIONS
    """

    local_path = get_local_path(local_globus_path)
    session_path = str(Path(session.subject.nickname, str(session.start_time),
                       '00' + str(session.number)))
    collection = 'alf/probe00'
    revision = None

    data_path = Path(local_path).joinpath(session_path, collection, revision or '')
    dsets = ['spikes.times', 'spikes.clusters', 'clusters.amps']
    dsets_list = create_data(dsets, data_path, size=200)

    data = {'created_by': username,
            'path': session_path,
            'filenames': [d.relative_to(local_path + session_path).as_posix()
                          for d in dsets_list],
            'server_only': False,
            'filesizes': [d.stat().st_size for d in dsets_list]}

    r = client.post(reverse('register-file'), data, SERVER_NAME='localhost:8000',
                    content_type='application/json')

    exp_files = []
    exp_files_uuid = []
    for data in r.data:
        exp_files.append(str(Path(session_path).joinpath(collection, revision or '',
                                                         data['name'])))
        exp_files_uuid.append(str(Path(session_path).joinpath(collection, (revision or ''),
                                  Path(data['name']).stem + '.' + str(data['id']) +
                                  Path(data['name']).suffix)))

    exp_files.sort()
    exp_files_uuid.sort()

    # Test bulk sync
    bulk_sync(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_sync(exp_files, lab_name=lab_name, revision_name='unknown', iteration=1)

    # Test bulk transfer, first in dry mode
    _, tm = _bulk_transfer(dry_run=True, lab=lab_name, gc=gtc)
    test_bulk_transfer_dry(tm, exp_files, exp_files_uuid, lab_name=lab_name)

    # Then in non dry mode
    _, tm = _bulk_transfer(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_transfer(exp_files, lab_name=lab_name, revision_name='unknown')

    # Test second iteration of bulksync
    bulk_sync(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_sync(exp_files, lab_name=lab_name, revision_name='unknown', iteration=2)

    # Check on flatiron to make sure files exist
    # This fails unless you clean up properly as version_testing folder also present
    test_flatiron_files_exist(exp_files_uuid, gtc, lab_name=lab_name)

    """
    TEST TRANSFER OF DATA WITH REVISIONS
    """

    revision = 'version_testing'
    data_path = Path(local_path).joinpath(session_path, collection, revision or '')
    dsets = ['spikes.times', 'spikes.clusters', 'clusters.amps']
    dsets_list = create_data(dsets, data_path, size=150)

    data = {'created_by': username,
            'path': session_path,
            'filenames': [d.relative_to(local_path + session_path).as_posix()
                          for d in dsets_list],
            'server_only': False,
            'revisions': [revision for d in dsets_list],
            'filesizes': [d.stat().st_size for d in dsets_list]}

    r = client.post(reverse('register-file'), data, SERVER_NAME='localhost:8000',
                    content_type='application/json')

    exp_files = []
    exp_files_uuid = []
    for data in r.data:
        exp_files.append(str(Path(session_path).joinpath(collection, revision or '',
                                                         data['name'])))
        exp_files_uuid.append(str(Path(session_path).joinpath(collection, (revision or ''),
                                  Path(data['name']).stem + '.' + str(data['id']) +
                                  Path(data['name']).suffix)))
    exp_files.sort()
    exp_files_uuid.sort()

    bulk_sync(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_sync(exp_files, lab_name=lab_name, revision_name=revision, iteration=1)

    _, tm = _bulk_transfer(dry_run=True, lab=lab_name, gc=gtc)
    test_bulk_transfer_dry(tm, exp_files, exp_files_uuid, lab_name=lab_name)

    _, tm = _bulk_transfer(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_transfer(exp_files, lab_name=lab_name, revision_name=revision)

    # TODO maybe add in a brief pause

    bulk_sync(dry_run=False, lab=lab_name, gc=gtc)
    test_bulk_sync(exp_files, lab_name=lab_name, revision_name=revision, iteration=2)

    # This needs a bit of time (maybe don't bother)
    test_flatiron_files_exist(exp_files_uuid, gtc, lab_name=lab_name)

    """
    TEST DELETING DATA
    """
    # Test deletion of local files globus_delete_local_datasets
    dsets_to_del = Dataset.objects.filter(session__lab__name=lab_name,
                                          name='clusters.amps.npy', revision__name='unknown')
    frs = FileRecord.objects.filter(dataset__in=dsets_to_del)
    frs_local = frs.filter(data_repository__globus_is_personal=True)
    exp_files = [fr.data_repository.globus_path + fr.relative_path for fr in frs_local]

    test_delete_datasets(dsets_to_del, before_del=True)

    # Run in dry mode and check you get the correct
    dm = globus_delete_local_datasets(dsets_to_del, dry=True, gc=gtc)
    assert(dm['endpoint'] == local_endpoint_id)
    assert(dm['DATA'][0]['path'] == exp_files[0])
    # Make sure dry mode hasn't actually deleted anything
    test_delete_datasets(dsets_to_del, before_del=True)

    globus_delete_local_datasets(dsets_to_del, dry=False, gc=gtc)
    # Test that the local filerecords have been deleted
    test_delete_datasets(dsets_to_del, local_only=True)

    # Make sure the dataset has been deleted on local endpoint
    ls_local = gtc.operation_ls(local_endpoint_id, path=str(Path(exp_files[0]).parent))
    ls_files = [ls['name'] for ls in ls_local['DATA']]
    assert(not Path(exp_files[0]).name in ls_files)

    dsets_to_del = Dataset.objects.filter(session__lab__name=lab_name, name='spikes.clusters.npy',
                                          revision__name='unknown')
    revision = None

    # Change the size of spikes.clusters on local endpoint
    data_path = Path(local_path).joinpath(session_path, collection, revision or '')
    dsets = ['spikes.clusters']
    _ = create_data(dsets, data_path, size=300)

    dm = globus_delete_local_datasets(dsets_to_del, dry=True, gc=gtc)
    assert(dm == [])
    test_delete_datasets(dsets_to_del, before_del=True)
    globus_delete_local_datasets(dsets_to_del, dry=False, gc=gtc)
    # As the delete should have failed we expect to be the same as before we ran delete command
    test_delete_datasets(dsets_to_del, before_del=True)

    # Now test the globus_delete_datasets
    dsets_to_del = Dataset.objects.filter(session__lab__name=lab_name,
                                          revision__name='version_testing')
    frs = FileRecord.objects.filter(dataset__in=dsets_to_del)
    frs_local = frs.filter(data_repository__globus_is_personal=True)
    frs_server = frs.filter(data_repository__globus_is_personal=False)
    exp_files = [fr.data_repository.globus_path + fr.relative_path for fr in frs_local]
    exp_files_server = [fr.data_repository.globus_path + fr.relative_path for fr in frs_server]

    # Try the local only with dry = True
    file_to_del = globus_delete_datasets(dsets_to_del, dry=True, local_only=True, gc=gtc)
    assert(all([file == exp for file, exp in zip(file_to_del, exp_files)]))
    # Make sure non have been deleted
    test_delete_datasets(dsets_to_del, before_del=True)

    # Now with dry=False
    globus_delete_datasets(dsets_to_del, dry=False, local_only=True, gc=gtc)
    test_delete_datasets(dsets_to_del, local_only=True)

    ls_local = gtc.operation_ls(local_endpoint_id, path=str(Path(exp_files[0]).parent))
    assert(len(ls_local['DATA']) == 0)

    # Now delete off the server too
    globus_delete_datasets(dsets_to_del, dry=False, local_only=False, gc=gtc)
    test_delete_datasets(dsets_to_del, local_only=False)

    ls_flatiron = gtc.operation_ls(flatiron_endpoint_id,
                                   path=str(Path(exp_files_server[0]).parent))
    assert(len(ls_flatiron['DATA']) == 0)

    # IS THIS POTENTIALLY TOO DANGEROSUS
    dsets_to_del = Dataset.objects.filter(session__lab__name=lab_name)
    assert(dsets_to_del.count() == 3)
    globus_delete_datasets(dsets_to_del, dry=False, local_only=False, gc=gtc)
    test_delete_datasets(dsets_to_del, local_only=False)

    # TODO clean up


def test_delete_datasets(dsets2del, local_only=True, before_del=False):
    """
    Tests transfers.globus_delete_local_datasets and transfers.globus_delete_datasets

    :param dsets2del: query set of datasets to delete
    :param local_only: if deletion has only been conducted on lcoal server
    :param before_del: to test datasets and filerecords before any deletion. Can be used for
    example after dry=True to make sure dry run hasn't deleted anything
    :return:
    """
    if before_del:
        # Checks datasets before deletion or if deletion run in dry mode
        dsets = Dataset.objects.filter(pk__in=dsets2del.values_list('id', flat=True))
        assert (dsets.count() == dsets2del.count())
        # But the local file records to have been deleted
        frs = FileRecord.objects.filter(dataset__in=dsets2del)
        assert (frs.count() == 2 * dsets2del.count())

        return

    if local_only:
        dsets = Dataset.objects.filter(pk__in=dsets2del.values_list('id', flat=True))
        assert (dsets.count() == dsets2del.count())
        # But the local file records to have been deleted
        frs = FileRecord.objects.filter(dataset__in=dsets2del)
        assert (frs.count() == dsets2del.count())
        assert (all([not fr.data_repository.globus_is_personal for fr in frs]))
    else:
        dsets = Dataset.objects.filter(pk__in=dsets2del.values_list('id', flat=True))
        assert (dsets.count() == 0)
        # But the local file records to have been deleted
        frs = FileRecord.objects.filter(dataset__in=dsets2del)
        assert (frs.count() == 0)


def create_data(dsets, data_path, size=100):
    """
    Creates fake data np.random.rand(size) with location given by data_path and names give in
    dsets

    :param dsets: list of dataset names e.g ['spikes.clusters', 'spikes.times']
    :param data_path: path to local folder to save datasets
    :param size: size of data
    :return: list of datasets with full path
    """
    data_path = Path(data_path)
    data_path.mkdir(exist_ok=True, parents=True)

    dsets_list = []
    for dset in dsets:
        rand_data = np.random.rand(size)
        np.save(data_path.joinpath(dset + '.npy'), rand_data)
        dsets_list.append(data_path.joinpath(dset + '.npy'))

    return dsets_list


def test_bulk_sync(expected_files, lab_name='testlab', revision_name='unknown', iteration=1):
    """
    Test transfers.bulk_sync function in dry=False mode

    :param expected_files: list of expected filenames str(session, collection, revision, name)
    :param lab_name: name of lab
    :param revision_name: name of revision
    :param iteration: whether it is the first or second time the bulk sync function is called in
    the transfer pipeline
    :return:
    """
    frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                           data_repository__globus_is_personal=True,
                                           dataset__revision__name=revision_name).
                 order_by('dataset__name'))
    frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                              data_repository__globus_is_personal=False,
                                              dataset__revision__name=revision_name).
                    order_by('dataset__name'))

    # Check all is as expected in the local server filerecords
    assert(frs_local.count() == len(expected_files))
    assert(all([fr.exists for fr in frs_local]))
    assert (all([fr.relative_path == expected_files[iF] for iF, fr in enumerate(frs_local)]))
    assert(all([not fr.json for fr in frs_local]))

    # Check all is as expected in the flatiron filerecords
    assert(frs_flatiron.count() == len(expected_files))
    if iteration == 1:
        assert(all([not fr.exists for fr in frs_flatiron]))
    else:
        assert (all([fr.exists for fr in frs_flatiron]))
    assert (all([fr.relative_path == expected_files[iF] for iF, fr in
                 enumerate(frs_flatiron)]))
    assert (all([not fr.json for fr in frs_flatiron]))


def test_bulk_transfer_dry(tm, expected_files, expected_files_uuid, lab_name='testlab'):
    """
    Tests transfers._bulk_transfer in dry=True mode

    :param tm: transfer matrix of file transfers (output from transfers._bulk_transfer)
    :param expected_files: list of expected filenames str(session, collection, revision, name)
    :param expected_files_uuid: list of expected filenames with dataset uuid str(session,
    collection, revision, name + uuid)
    :param lab_name: name of lab
    :return:
    """
    data_repo_local = DataRepository.objects.filter(lab__name=lab_name,
                                                    globus_is_personal=True).first()
    data_repo_flatiron = DataRepository.objects.filter(lab__name=lab_name,
                                                       globus_is_personal=False).first()
    # Get entry in transfer matrix that is non zero
    tm_data = tm[np.where(tm != 0)[0], np.where(tm != 0)[1]][0]
    # Make sure the endpoints have been setup correctly
    assert (tm_data['source_endpoint'] == data_repo_local.globus_endpoint_id)
    assert(tm_data['destination_endpoint'] == data_repo_flatiron.globus_endpoint_id)
    # Make sure the transfer label is instructive
    assert(tm_data['label'] == f'{data_repo_local.name} to {data_repo_flatiron.name}')
    # Check individual file transfers
    for it, t in enumerate(tm_data['DATA']):
        assert(t['source_path'] == data_repo_local.globus_path + expected_files[it])
        assert(t['destination_path'] in data_repo_flatiron.globus_path + expected_files_uuid[it])


def test_bulk_transfer(expected_files, lab_name='testlab', revision_name='unknown'):
    """
    Tests transfers._bulk_transfer in dry=False mode

    :param expected_files: list of expected filenames str(session, collection, revision, name)
    :param lab_name: name of lab
    :param revision_name: name of revision
    :return:
    """
    frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                           data_repository__globus_is_personal=True,
                                           dataset__revision__name=revision_name).
                 order_by('dataset__name'))
    frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                              data_repository__globus_is_personal=False,
                                              dataset__revision__name=revision_name).
                    order_by('dataset__name'))

    # Check local server file records haven't changes
    assert(frs_local.count() == len(expected_files))
    assert(all([fr.exists for fr in frs_local]))
    assert(all([not fr.json for fr in frs_local]))

    # Check the flatiron server filerecords are as expected
    assert(frs_flatiron.count() == len(expected_files))
    # Expect flags to still be exists = False
    assert(all([not fr.exists for fr in frs_flatiron]))
    # We expect there to be json with transfer_pending states
    assert(all([fr.json.get('transfer_pending') for fr in frs_flatiron]))


def test_flatiron_files_exist(expected_files_uuid, gtc, lab_name='testlab'):
    """
    Test that physical files exist on flatiron

    :param expected_files_uuid: list of expected filenames with dataset uuid str(session,
    collection, revision, name + uuid)
    :param gtc: globus transfer client
    :param lab_name: name of lab
    :return:
    """

    data_repo_flatiron = DataRepository.objects.filter(lab__name=lab_name,
                                                       globus_is_personal=False).first()
    print(data_repo_flatiron)
    print(data_repo_flatiron.globus_endpoint_id)
    files_flatiron = gtc.operation_ls(data_repo_flatiron.globus_endpoint_id,
                                      path=data_repo_flatiron.globus_path +
                                      str(Path(expected_files_uuid[0]).parent))

    for iF, file in enumerate(files_flatiron['DATA']):
        assert(file['name'] == Path(expected_files_uuid[iF]).name)
