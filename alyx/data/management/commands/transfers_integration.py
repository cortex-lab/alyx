from misc.models import Lab, LabLocation, LabMember
from data.models import DataRepository, DataRepositoryType, FileRecord, Dataset
from data.transfers import (bulk_sync, _bulk_transfer, globus_delete_local_datasets,
                            globus_delete_datasets)
from subjects.models import Subject
from actions.models import Session
from django.urls import reverse
from django.test import Client
from django.core.management import BaseCommand
from django.db.models import Q

import os
import numpy as np
from pathlib import Path
import json
import globus_sdk as globus
import time

import traceback

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
    message = 'Please make a config-paths file in ./globus/lta that contains the ' \
              'folder on your local endpoint accessible by globus e.g echo "/mnt/s0/Data" > ' \
              '~/.globusonline/lta/config-paths'
    assert config_path.joinpath("config-paths").exists(), message
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


class TestTransfers(object):

    def setUp(self) -> None:

        # Make sure we can log in
        self.gtc = globus_login(GLOBUS_CLIENT_ID)
        assert self.gtc

        # Check that the local endpoint is connected
        self.local_endpoint_id = get_local_endpoint()
        endpoint_info = self.gtc.get_endpoint(self.local_endpoint_id)
        assert endpoint_info['gcp_connected']

        # Check that the flatiron endpoint is connected
        self.flatiron_endpoint_id = (DataRepository.objects.filter(globus_is_personal=False,
                                                                   name__icontains='flatiron').
                                     first().globus_endpoint_id)
        endpoint_info = self.gtc.get_endpoint(self.flatiron_endpoint_id)
        assert endpoint_info['gcp_connected'] is not False

        # Make sure we have the correct accessible local globus path
        local_globus_path = get_local_globus_path()
        assert self.gtc.operation_ls(self.local_endpoint_id, path=local_globus_path)

        # Connect to client and check we can log in properly
        client = Client()
        self.client = client_login(client)
        _ = client.get(path='/', SERVER_NAME=SERVER_NAME)
        # assert(r.status_code == 200)

        # Create a test lab
        self.lab_name = 'testlab'
        self.lab, _ = Lab.objects.get_or_create(name=f'{self.lab_name}')

        # Create a lab location in test lab
        lab_location, _ = LabLocation.objects.get_or_create(name=f'{self.lab_name}_location',
                                                            lab=self.lab)

        # Create a testlab user
        self.username = f'{self.lab_name}_user'
        self.user, _ = LabMember.objects.get_or_create(username=self.username)

        # Create data repositories for the test lab
        # 1. For flatiron
        repo_type = DataRepositoryType.objects.get(name='Fileserver')
        name = f'flatiron_{self.lab_name}'
        hostname = 'ibl.flatironinstitute.org'
        data_url = f'https://ibl.flatironinstitute.org/{self.lab_name}/Subjects/'
        self.flatiron_globus_path = f'/{self.lab_name}/Subjects/'
        globus_is_personal = False
        self.flatiron_data_repo, _ = DataRepository.\
            objects.get_or_create(name=name, repository_type=repo_type, hostname=hostname,
                                  data_url=data_url, globus_path=self.flatiron_globus_path,
                                  globus_endpoint_id=self.flatiron_endpoint_id,
                                  globus_is_personal=globus_is_personal)

        # 2. For local server
        name = f'{self.lab_name}_SR'
        globus_is_personal = True
        self.local_globus_path = str(Path(local_globus_path).joinpath(self.lab_name,
                                                                      'Subjects')) + '/'
        self.local_data_repo, _ = DataRepository.\
            objects.get_or_create(name=name, repository_type=repo_type,
                                  globus_path=self.local_globus_path,
                                  globus_endpoint_id=self.local_endpoint_id,
                                  globus_is_personal=globus_is_personal)

        # 3. Make an aws file server
        name = f'aws_{self.lab_name}'
        globus_is_personal = False
        hostname = f'aws_{self.lab_name}'
        data_url = 'http://whatever.com/'
        aws_globus_path = f'/data/{self.lab_name}/Subjects/'
        self.aws_data_repo, _ = DataRepository.\
            objects.get_or_create(name=name, repository_type=repo_type, hostname=hostname,
                                  data_url=data_url, globus_path=aws_globus_path,
                                  globus_endpoint_id=self.flatiron_endpoint_id,
                                  globus_is_personal=globus_is_personal)

        # Add the data repos to the lab
        self.lab.repositories.add(self.flatiron_data_repo)
        self.lab.repositories.add(self.local_data_repo)
        self.lab.repositories.add(self.aws_data_repo)
        self.lab.save()

        # Now make a subject matched to the lab
        nickname = f'{self.lab_name}_001'
        subject, _ = Subject.objects.get_or_create(nickname=nickname, lab=self.lab,
                                                   responsible_user=self.user)

        # And a session associated with the subject
        self.session, _ = Session.objects.get_or_create(subject=subject, location=lab_location,
                                                        lab=self.lab, start_time='2021-03-03',
                                                        number=1)

        self.session_path = str(Path(self.session.subject.nickname,
                                     str(self.session.start_time),
                                     '00' + str(self.session.number)))

    def test_transfers(self):

        """
        TEST TRANSFER OF DATA WITH NO REVISIONS
        """
        local_path = get_local_path(self.local_globus_path)
        collection = 'alf/probe00'
        revision = None

        data_path = Path(local_path).joinpath(self.session_path, collection, revision or '')

        dsets = ['spikes.times', 'spikes.clusters', 'spikes.amps', 'clusters.amps',
                 'clusters.waveforms']
        dsets_list = create_data(dsets, data_path, size=200)

        data = {'created_by': self.username,
                'path': self.session_path,
                'filenames': [d.relative_to(local_path + self.session_path).as_posix()
                              for d in dsets_list],
                'server_only': False,
                'filesizes': [d.stat().st_size for d in dsets_list]}

        r = self.client.post(reverse('register-file'), data, SERVER_NAME=SERVER_NAME,
                             content_type='application/json')

        exp_files = []
        exp_files_uuid = []
        for data in r.data:
            exp_files.append(str(Path(self.session_path).joinpath(collection, revision or '',
                                                                  data['name'])))
            exp_files_uuid.append(str(Path(self.session_path).joinpath(collection,
                                                                       (revision or ''),
                                      Path(data['name']).stem + '.' + str(data['id']) +
                                      Path(data['name']).suffix)))

        exp_files.sort()
        exp_files_uuid.sort()

        # Set the aws file records to True to confuse things
        dsets = Dataset.objects.filter(session__lab__name=self.lab_name)
        frs = FileRecord.objects.filter(dataset__in=dsets, data_repository__name__icontains='aws')
        frs.update(exists=True)

        # Test bulk sync
        bulk_sync(dry_run=False, lab=self.lab_name, gc=self.gtc)
        self.assert_bulk_sync(exp_files, lab_name=self.lab_name, revision_name=None,
                              iteration=1)

        # Test bulk transfer, first in dry mode
        _, tm = _bulk_transfer(dry_run=True, lab=self.lab_name, gc=self.gtc)
        self.assert_bulk_transfer_dry(tm, exp_files, exp_files_uuid, lab_name=self.lab_name)
#
        # Then in non dry mode
        _, tm = _bulk_transfer(dry_run=False, lab=self.lab_name, gc=self.gtc)
        self.assert_bulk_transfer(exp_files, lab_name=self.lab_name, revision_name=None)

        time.sleep(40)

        # Test second iteration of bulksync
        bulk_sync(dry_run=False, lab=self.lab_name, gc=self.gtc)
        self.assert_bulk_sync(exp_files, lab_name=self.lab_name, revision_name=None,
                              iteration=2)

        """
        TEST DELETING DATA
        """
        # Test deletion of local files globus_delete_local_datasets
        dsets_to_del = Dataset.objects.filter(session__lab__name=self.lab_name,
                                              name='spikes.amps.npy')
        frs = FileRecord.objects.filter(dataset__in=dsets_to_del)
        frs_local = frs.filter(data_repository__globus_is_personal=True)
        exp_files = [fr.data_repository.globus_path + fr.relative_path for fr in frs_local]

        self.assert_delete_datasets(dsets_to_del, before_del=True)

        # Run in dry mode and check you get the correct
        dm = globus_delete_local_datasets(dsets_to_del, dry=True, gc=self.gtc)
        assert dm['endpoint'] == self.local_endpoint_id
        assert dm['DATA'][0]['path'] == exp_files[0]
        # Make sure dry mode hasn't actually deleted anything
        self.assert_delete_datasets(dsets_to_del, before_del=True)

        globus_delete_local_datasets(dsets_to_del, dry=False, gc=self.gtc)
        # Test that the local filerecords have been deleted
        self.assert_delete_datasets(dsets_to_del, local_only=True)

        time.sleep(5)
        # Make sure the dataset has been deleted on local endpoint
        ls_local = self.gtc.operation_ls(self.local_endpoint_id,
                                         path=str(Path(exp_files[0]).parent))
        ls_files = [ls['name'] for ls in ls_local['DATA']]
        assert not Path(exp_files[0]).name in ls_files

        dsets_to_del = Dataset.objects.filter(session__lab__name=self.lab_name,
                                              name='spikes.times.npy')

        revision = None
        # Change the size of spikes.clusters on local endpoint
        data_path = Path(local_path).joinpath(self.session_path, collection, revision or '')
        dsets = ['spikes.times']
        _ = create_data(dsets, data_path, size=300)

        dm = globus_delete_local_datasets(dsets_to_del, dry=True, gc=self.gtc)
        assert dm == []
        self.assert_delete_datasets(dsets_to_del, before_del=True)
        globus_delete_local_datasets(dsets_to_del, dry=False, gc=self.gtc)
        # As the delete should have failed we expect to be the same as before we ran delete command
        self.assert_delete_datasets(dsets_to_del, before_del=True)

        # Now test the globus_delete_datasets
        dsets_to_del = Dataset.objects.filter(session__lab__name=self.lab_name,
                                              name__icontains='clusters')
        frs = FileRecord.objects.filter(dataset__in=dsets_to_del)
        frs_local = frs.filter(data_repository__globus_is_personal=True).order_by('dataset__name')
        frs_server = (frs.filter(data_repository__globus_is_personal=False,
                                 data_repository__name__icontains='flatiron').
                      order_by('dataset__name'))
        exp_files = [fr.data_repository.globus_path + fr.relative_path for fr in frs_local]
        exp_files_server = [fr.data_repository.globus_path + fr.relative_path for fr in frs_server]

        # Try the local only with dry = True
        file_to_del = globus_delete_datasets(dsets_to_del, dry=True, local_only=True, gc=self.gtc)
        assert all(file == exp for file, exp in zip(file_to_del, exp_files))
        # Make sure non have been deleted
        self.assert_delete_datasets(dsets_to_del, before_del=True)

        # Now with dry=False
        globus_delete_datasets(dsets_to_del, dry=False, local_only=True, gc=self.gtc)
        self.assert_delete_datasets(dsets_to_del, local_only=True)

        time.sleep(5)
        ls_local = self.gtc.operation_ls(self.local_endpoint_id,
                                         path=str(Path(exp_files[0]).parent))
        # have spikes.times left
        assert len(ls_local['DATA']) == 1

        # Now delete off the server too
        globus_delete_datasets(dsets_to_del, dry=False, local_only=False, gc=self.gtc)
        self.assert_delete_datasets(dsets_to_del, local_only=False)
        time.sleep(5)
        ls_flatiron = self.gtc.operation_ls(self.flatiron_endpoint_id,
                                            path=str(Path(exp_files_server[0]).parent))
        # have spikes.times and spikes.amps left
        assert len(ls_flatiron['DATA']) == 2

    @staticmethod
    def assert_delete_datasets(dsets2del, local_only=True, before_del=False):
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
            frs = FileRecord.objects.filter(~Q(data_repository__name__icontains='aws'),
                                            dataset__in=dsets2del)
            assert (frs.count() == 2 * dsets2del.count())

            return

        if local_only:
            dsets = Dataset.objects.filter(pk__in=dsets2del.values_list('id', flat=True))
            assert (dsets.count() == dsets2del.count())
            # But the local file records to have been deleted
            frs = FileRecord.objects.filter(~Q(data_repository__name__icontains='aws'),
                                            dataset__in=dsets2del)
            assert (frs.count() == dsets2del.count())
            assert (all([not fr.data_repository.globus_is_personal for fr in frs]))
        else:
            dsets = Dataset.objects.filter(pk__in=dsets2del.values_list('id', flat=True))
            assert (dsets.count() == 0)
            # But the local file records to have been deleted
            frs = FileRecord.objects.filter(~Q(data_repository__name__icontains='aws'),
                                            dataset__in=dsets2del)
            assert (frs.count() == 0)

    @staticmethod
    def assert_bulk_sync(expected_files, lab_name='testlab', revision_name=None, iteration=1):
        """
        Test transfers.bulk_sync function in dry=False mode

        :param expected_files: list of expected filenames str(session, collection, revision, name)
        :param lab_name: name of lab
        :param revision_name: name of revision
        :param iteration: whether it is the first or second time the bulk sync function is called
        in the transfer pipeline
        :return:
        """
        if not revision_name:
            frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                   data_repository__globus_is_personal=True,
                                                   dataset__revision__isnull=True).
                         order_by('dataset__name'))
            frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                      data_repository__globus_is_personal=False,
                                                      data_repository__name__icontains='flatiron',
                                                      dataset__revision__isnull=True).
                            order_by('dataset__name'))

        else:
            frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                   data_repository__globus_is_personal=True,
                                                   dataset__revision__name=revision_name).
                         order_by('dataset__name'))
            frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                      data_repository__globus_is_personal=False,
                                                      data_repository__name__icontains='flatiron',
                                                      dataset__revision__name=revision_name).
                            order_by('dataset__name'))

        # Check all is as expected in the local server filerecords
        assert (frs_local.count() == len(expected_files))
        assert (all([fr.exists for fr in frs_local]))
        assert (all([fr.relative_path == expected_files[iF] for iF, fr in enumerate(frs_local)]))
        assert (all([not fr.json for fr in frs_local]))

        # Check all is as expected in the flatiron filerecords
        assert (frs_flatiron.count() == len(expected_files))
        if iteration == 1:
            assert (all([not fr.exists for fr in frs_flatiron]))
        else:
            assert (all([fr.exists for fr in frs_flatiron]))
        assert (all([fr.relative_path == expected_files[iF] for iF, fr in
                     enumerate(frs_flatiron)]))
        assert (all([not fr.json for fr in frs_flatiron]))

    @staticmethod
    def assert_bulk_transfer_dry(tm, expected_files, expected_files_uuid, lab_name='testlab'):
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
                                                           name__icontains='flatiron',
                                                           globus_is_personal=False).first()
        # Get entry in transfer matrix that is non zero
        tm_data = tm[np.where(tm != 0)[0], np.where(tm != 0)[1]][0]
        # Make sure the endpoints have been setup correctly
        assert (tm_data['source_endpoint'] == data_repo_local.globus_endpoint_id)
        assert (tm_data['destination_endpoint'] == data_repo_flatiron.globus_endpoint_id)
        # Make sure the transfer label is instructive
        assert (tm_data['label'] == f'{data_repo_local.name} to {data_repo_flatiron.name}')
        # Check individual file transfers
        for it, t in enumerate(tm_data['DATA']):
            assert (t['source_path'] == data_repo_local.globus_path + expected_files[it])
            assert (t['destination_path'] in data_repo_flatiron.globus_path +
                    expected_files_uuid[it])

    @staticmethod
    def assert_bulk_transfer(expected_files, lab_name='testlab', revision_name=None):
        """
        Tests transfers._bulk_transfer in dry=False mode

        :param expected_files: list of expected filenames str(session, collection, revision, name)
        :param lab_name: name of lab
        :param revision_name: name of revision
        :return:
        """
        if not revision_name:
            frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                   data_repository__globus_is_personal=True,
                                                   dataset__revision__isnull=True).
                         order_by('dataset__name'))
            frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                      data_repository__globus_is_personal=False,
                                                      data_repository__name__icontains='flatiron',
                                                      dataset__revision__isnull=True).
                            order_by('dataset__name'))

        else:
            frs_local = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                   data_repository__globus_is_personal=True,
                                                   dataset__revision__name=revision_name).
                         order_by('dataset__name'))
            frs_flatiron = (FileRecord.objects.filter(data_repository__lab__name=lab_name,
                                                      data_repository__globus_is_personal=False,
                                                      data_repository__name__icontains='flatiron',
                                                      dataset__revision__name=revision_name).
                            order_by('dataset__name'))

        # Check local server file records haven't changes
        assert (frs_local.count() == len(expected_files))
        assert (all([fr.exists for fr in frs_local]))
        assert (all([not fr.json for fr in frs_local]))

        # Check the flatiron server filerecords are as expected
        assert (frs_flatiron.count() == len(expected_files))
        # Expect flags to still be exists = False
        assert (all([not fr.exists for fr in frs_flatiron]))
        # We expect there to be json with transfer_pending states
        assert (all([fr.json.get('transfer_pending') for fr in frs_flatiron]))

    def tearDown(self) -> None:

        # Delete the session folders on flatiron and on local computer
        # Delete from local computer
        local_delete = globus.DeleteData(self.gtc, self.local_endpoint_id, recursive=True)
        local_delete.add_item(self.local_globus_path + self.session_path)
        self.gtc.submit_delete(local_delete)

        # Delete from flatiron
        flatiron_delete = globus.DeleteData(self.gtc, str(self.flatiron_endpoint_id),
                                            recursive=True)
        flatiron_delete.add_item(self.flatiron_globus_path + self.session_path)
        self.gtc.submit_delete(flatiron_delete)

        # Delete from flatiron
        flatiron_delete = globus.DeleteData(self.gtc, str(self.flatiron_endpoint_id),
                                            recursive=True)
        flatiron_delete.add_item(self.flatiron_globus_path + self.session_path)
        self.gtc.submit_delete(flatiron_delete)

        # Remove lab from database, this also deletes lab location, session and subject
        self.lab.delete()

        # Remove data repos
        self.local_data_repo.delete()
        self.flatiron_data_repo.delete()

        # Remove the user
        self.user.delete()


class Command(BaseCommand):
    """
    Run in the following way
    python ./manage.py transfers_integration run_tests
    """
    def add_arguments(self, parser):
        parser.add_argument('action', help='Action')

    def handle(self, *args, **options):
        action = options.get('action')

        if action == 'run_tests':
            int_test = TestTransfers()
            int_test.setUp()
            try:
                int_test.test_transfers()
            except Exception:
                trace_back = traceback.format_exc()
                print(trace_back)
            int_test.tearDown()
