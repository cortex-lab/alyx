from random import random, choice, randint

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from django.db import transaction

from alyx.base import BaseTests
from actions.models import Session, ProcedureType
from misc.models import Lab
from subjects.models import Subject
from experiments.models import ProbeInsertion, ImagingType
from data.models import Dataset, DatasetType, Tag


class APIProbeExperimentTests(BaseTests):

    def setUp(self):
        call_command('loaddata', 'experiments/fixtures/experiments.probemodel.json', verbosity=0)
        call_command('loaddata', 'experiments/fixtures/experiments.brainregion.json', verbosity=0)
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.session = Session.objects.first()
        # need to add ephys procedure
        self.session.task_protocol = 'ephys'
        self.session.save()
        self.dict_insertion = {'session': str(self.session.id),
                               'name': 'probe_00',
                               'model': '3A'}

    def test_brain_regions_rest_filter(self):
        # test the custom filters get_descendants and get_ancestors
        url = reverse('brainregion-list')
        br = self.ar(self.client.get(url + "?ancestors=688"))
        self.assertTrue(len(br) == 4)
        br = self.ar(self.client.get(url + "?ancestors=CTX"))
        self.assertTrue(len(br) == 4)
        response = self.client.get(url + "?descendants=688")
        self.assertTrue(response.status_code == 200)
        self.assertTrue(response.data['count'] == 567)

    def test_brain_regions_rest(self):
        # test the list view
        url = reverse('brainregion-list')
        br = self.ar(self.client.get(url + "?id=687"))
        self.assertTrue(len(br) == 1 and br[0]['id'] == 687)
        brs = self.ar(self.client.get(url + "?name=retrosplenial"))
        self.assertTrue(len(brs) > 15)  # at least 15 brain areas retrosplenial
        brs = self.ar(self.client.get(url + "?parent=315"))
        self.assertTrue(set(br['parent'] for br in brs) == {315} and len(brs) > 10)
        # test the details view
        url_id = reverse('brainregion-detail', args=[687])
        br2 = self.ar(self.client.get(url_id))
        self.assertTrue(br[0] == br2)
        # test patching the description
        self.ar(self.patch(url_id, data={'description': 'I was there'}))
        br3 = self.ar(self.client.get(url_id))
        self.assertTrue(br3['description'] == 'I was there')
        # add a description to the parent
        parent = self.ar(self.client.get(reverse('brainregion-detail', args=[br3['parent']])))
        self.ar(self.patch(
            reverse('brainregion-detail', args=[parent['parent']]),
            data={'description': 'grandpa'}))
        parent = self.ar(self.client.get(reverse('brainregion-detail', args=[br3['parent']])))
        self.assertTrue(len(parent['related_descriptions']) == 2)
        # and makes sure one can't patch anything else
        self.patch(url_id, data={'description': 'I was there', 'acronym': 'tutu'})
        br3 = self.ar(self.client.get(url_id))
        self.assertTrue(br3['acronym'] != 'tutu')

    def test_create_list_delete_probe_insertion(self):
        # test the create endpoint
        url = reverse('probeinsertion-list')
        response = self.post(url, self.dict_insertion)
        d = self.ar(response, 201)

        # test the list endpoint
        response = self.client.get(url)
        d = self.ar(response, 200)

        # test the session filter
        urlf = url + '?&session=' + str(self.session.id) + '&name=probe_00'
        response = self.client.get(urlf)
        dd = self.ar(response, 200)
        self.assertTrue(len(dd) == 1)
        urlf = url + '?&session=' + str(self.session.id) + '&name=probe_01'
        response = self.client.get(urlf)
        dd = self.ar(response, 200)
        self.assertTrue(dd == [])

        # test the delete endpoint
        response = self.client.delete(url + '/' + d[0]['id'])
        self.ar(response, 204)

    def test_probe_insertion_rest(self):
        # First create two insertions and attach to session
        probe_names = ['probe00', 'probe01']
        insertions = []
        for name in probe_names:
            insertion = {'session': str(self.session.id),
                         'name': name,
                         'model': '3A'
                         }
            url = reverse('probeinsertion-list')
            insertions.append(self.ar(self.post(url, insertion), 201))

        # test the task_protocol filter
        urlf = (reverse('probeinsertion-list') + '?&task_protocol=ephy')
        probe_ins = self.ar(self.client.get(urlf))
        self.assertTrue(len(probe_ins) == 2)
        urlf = (reverse('probeinsertion-list') + '?&task_protocol=training')
        probe_ins = self.ar(self.client.get(urlf))
        self.assertTrue(len(probe_ins) == 0)

        # test the project filter
        urlf = (reverse('probeinsertion-list') + '?&project=brain_wide')
        probe_ins = self.ar(self.client.get(urlf))
        self.assertTrue(len(probe_ins) == 0)

    def test_probe_insertion_dataset_interaction(self):
        # First create two insertions and attach to session
        probe_names = ['probe00', 'probe01']
        insertions = []
        for name in probe_names:
            insertion = {'session': str(self.session.id),
                         'name': name,
                         'model': '3A'
                         }
            url = reverse('probeinsertion-list')
            insertions.append(self.ar(self.post(url, insertion), 201))

        # Need to make the dataformat and the dataset_type in database
        self.post(reverse('dataformat-list'), {'name': 'df', 'file_extension': '.-'})
        self.post(reverse('datasettype-list'), {'name': 'dset0', 'filename_pattern': '--'})
        self.post(reverse('datasettype-list'), {'name': 'dset1', 'filename_pattern': '-.'})

        # Now attach datasets to the session with collection that contains probe_names
        dsets = ['dset0', 'dset1', 'dset0', 'dset0']
        collection = ['probe00', 'probe00', 'probe01', 'probe02']
        for dset, col in zip(dsets, collection):
            data = {'name': dset,
                    'dataset_type': dset,
                    'data_format': 'df',
                    'file_size': 1234,
                    'collection': 'alf/' + str(col),
                    'subject': self.session.subject.nickname,
                    'date': str(self.session.start_time.date())
                    }
            url = reverse('dataset-list')
            self.ar(self.post(url, data), 201)

        # check that when datasets are created, they're assigned in the m2m
        for i in range(2):
            p = ProbeInsertion.objects.get(name=probe_names[0])
            d = Dataset.objects.filter(collection__endswith=probe_names[0])
            assert (set(p.datasets.all().values_list('pk', flat=True)) ==
                    set(d.values_list('pk', flat=True)))

        # check that when a probe is created post-hoc, datasets get assigned in the m2m
        p2 = ProbeInsertion.objects.create(session=self.session, name='probe02')
        assert (set(p2.datasets.all().values_list('pk', flat=True)) ==
                set(Dataset.objects.filter(
                    collection__endswith=p2.name).values_list('pk', flat=True)))
        p2.delete()

        # Test that probeinsertion details serializer returns datasets associated with probe
        urlf = (reverse('probeinsertion-detail', args=[insertions[0]['id']]))
        probe_ins = self.ar(self.client.get(urlf))
        self.assertTrue(len(probe_ins['datasets']) == 2)

        # Test that dataset filter with probe id returns datasets associated with probe
        urlf = (reverse('dataset-list') + '?&probe_insertion=' + insertions[0]['id'])
        datasets = self.ar(self.client.get(urlf))
        self.assertTrue(len(datasets) == 2)

    def test_create_list_delete_trajectory(self):
        # first create a probe insertion
        insertion = {'session': str(self.session.id),
                     'name': 'probe_00',
                     'model': '3A'}
        url = reverse('probeinsertion-list')
        response = self.post(url, insertion)
        alyx_insertion = self.ar(response, 201)

        # create a trajectory
        url = reverse('trajectoryestimate-list')
        tdict = {'probe_insertion': alyx_insertion['id'],
                 'x': -4521.2,
                 'y': 2415.0,
                 'z': 0,
                 'phi': 80,
                 'theta': 10,
                 'depth': 5000,
                 'roll': 0,
                 'provenance': 'Micro-manipulator',
                 }
        response = self.post(url, tdict)
        alyx_trajectory = self.ar(response, 201)

        # test the filter/list
        urlf = (url + '?&probe_insertion=' + alyx_insertion['id'] +
                '&provenance=Micro-manipulator')
        traj = self.ar(self.client.get(urlf))
        self.assertTrue(len(traj) == 1)

        urlf = (url + '?&probe_insertion=' + alyx_insertion['id'] +
                '&provenance=Planned')
        traj = self.ar(self.client.get(urlf))
        self.assertTrue(len(traj) == 0)

        # test the delete endpoint
        response = self.client.delete(url + '/' + alyx_trajectory['id'])
        self.ar(response, 204)

    def test_create_list_delete_channels(self):
        # create the probe insertion
        pi = self.ar(self.post(reverse('probeinsertion-list'), self.dict_insertion), 201)
        tdict = {'probe_insertion': pi['id'],
                 'x': -4521.2,
                 'y': 2415.0,
                 'z': 0,
                 'phi': 80,
                 'theta': 10,
                 'depth': 5000,
                 'roll': 0,
                 'provenance': 'Micro-manipulator',
                 }
        traj = self.ar(self.post(reverse('trajectoryestimate-list'), tdict), 201)
        # post a single channel
        channel_dict = {
            'x': 111.1,
            'y': -222.2,
            'z': 333.3,
            'axial': 20,
            'lateral': 40,
            'brain_region': 1133,
            'trajectory_estimate': traj['id']
        }
        self.ar(self.post(reverse('channel-list'), channel_dict), 201)
        # post a list of channels
        chs = [channel_dict.copy(), channel_dict.copy()]
        chs[0]['axial'] = 40
        chs[1]['axial'] = 60
        response = self.post(reverse('channel-list'), chs)
        data = self.ar(response, 201)
        self.assertEqual(len(data), 2)

    def test_chronic_insertion(self):

        serial = '19019101'
        chronic_dict = {'subject': self.session.subject.nickname,
                        'serial': serial,
                        'model': '3B2',
                        'name': 'probe00'
                        }

        ci = self.ar(self.post(reverse('chronicinsertion-list'), chronic_dict), 201)

        # create the probe insertion with a related chronic insertion,
        # first without the serial number and make sure it errors
        probe_dict = {'session': str(self.session.id),
                      'name': 'probe00',
                      'model': '3B2',
                      'chronic_insertion': ci['id']}
        self.ar(self.post(reverse('probeinsertion-list'), probe_dict), 400)

        # with wrong serial number make sure it also errors
        probe_dict['serial'] = serial + 'abc'
        self.ar(self.post(reverse('probeinsertion-list'), probe_dict), 400)

        probe_dict['serial'] = serial
        pi = self.ar(self.post(reverse('probeinsertion-list'), probe_dict), 201)

        # create a trajectory and attach it to the chronic insertion
        traj_dict = {'chronic_insertion': ci['id'],
                     'x': -4521.2,
                     'y': 2415.0,
                     'z': 0,
                     'phi': 80,
                     'theta': 10,
                     'depth': 5000,
                     'roll': 0,
                     'provenance': 'Ephys aligned histology track',
                     }

        traj = self.ar(self.post(reverse('trajectoryestimate-list'), traj_dict), 201)

        # Add a channel to the trajectory
        channel_dict = {
            'x': 111.1,
            'y': -222.2,
            'z': 333.3,
            'axial': 20,
            'lateral': 40,
            'brain_region': 1133,
            'trajectory_estimate': traj['id']
        }
        self.ar(self.post(reverse('channel-list'), channel_dict), 201)

        urlf = (reverse('chronicinsertion-detail', args=[ci['id']]))
        chronic_ins = self.ar(self.client.get(urlf))

        # make sure the probe insertion associated with the chronic is the one we expect
        self.assertTrue(chronic_ins['probe_insertion'][0]['id'] == pi['id'])

        # check there is a trajectory estimate associated with the chronic insertion
        url = reverse('trajectoryestimate-list')
        urlf = (url + '?&chronic_insertion=' + ci['id'])
        traj = self.ar(self.client.get(urlf))
        self.assertTrue(len(traj) == 1)
        self.assertTrue(traj[0]['provenance'] == 'Ephys aligned histology track')

        # test the chronic insertion filters
        url = reverse('chronicinsertion-list')
        urlf = (url + '?&atlas_id=1133')
        chron = self.ar(self.client.get(urlf))
        self.assertTrue(len(chron) == 1)

        url = reverse('chronicinsertion-list')
        urlf = (url + '?&atlas_id=150')
        chron = self.ar(self.client.get(urlf))
        self.assertTrue(len(chron) == 0)

        url = reverse('chronicinsertion-list')
        urlf = (url + '?probe=' + pi['id'])
        chron = self.ar(self.client.get(urlf))
        self.assertTrue(len(chron) == 1)

        url = reverse('chronicinsertion-list')
        urlf = (url + '?session=' + str(self.session.id))
        chron = self.ar(self.client.get(urlf))
        self.assertTrue(len(chron) == 1)

    def test_dataset_filters(self):

        # make a probe insertion
        url = reverse('probeinsertion-list')
        response = self.post(url, self.dict_insertion)
        probe = self.ar(response, 201)

        # test dataset type filters
        dtype1, _ = DatasetType.objects.get_or_create(name='spikes.times')
        dtype2, _ = DatasetType.objects.get_or_create(name='clusters.amps')
        tag, _ = Tag.objects.get_or_create(name='tag_test')

        d1 = Dataset.objects.create(session=self.session, name='spikes.times.npy',
                                    dataset_type=dtype1, collection='alf/probe_00')
        Dataset.objects.create(session=self.session, name='clusters.amps.npy',
                               dataset_type=dtype2, collection='alf/probe_00')
        d1.tags.add(tag)
        d1.save()

        d = self.ar(self.client.get(reverse('probeinsertion-list') +
                                    '?dataset_types=spikes.times'))
        self.assertEqual(len(d), 1)
        self.assertEqual(probe['id'], d[0]['id'])

        q = '?dataset_types=spikes.times,clusters.amps'  # Check with list
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1)
        self.assertEqual(probe['id'], d[0]['id'])

        q += ',spikes.amps'
        self.assertFalse(self.ar(self.client.get(reverse('probeinsertion-list') + q)))

        # test dataset filters
        q = '?datasets=spikes.times.npy'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1)
        self.assertEqual(probe['id'], d[0]['id'])

        q = '?datasets=clusters.amps'
        self.assertFalse(self.ar(self.client.get(reverse('probeinsertion-list') + q)))

        # test filtering by tag
        q = '?tag=tag_test'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1)
        self.assertEqual(probe['id'], d[0]['id'])


class APIImagingExperimentTests(BaseTests):

    def setUp(self):
        call_command('loaddata', 'experiments/fixtures/experiments.brainregion.json', verbosity=0)
        call_command(
            'loaddata', 'experiments/fixtures/experiments.coordinatesystem.json', verbosity=0
        )
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        # self.session = Session.objects.first()
        lab = Lab.objects.create(name='lab')
        subject = Subject.objects.create(name='586', lab=lab)
        self.session = Session.objects.create(subject=subject, number=1)
        # need to add imaging procedure
        self.session.procedures.add(ProcedureType.objects.get_or_create(name='Imaging')[0])
        self.session.save()
        # add an imaging type
        ImagingType.objects.get_or_create(name='2P')
        self.dict_fov = {'session': str(self.session.id),
                         'imaging_type': '2P',
                         'name': 'FOV_00'}

    def test_create_list_delete_fov(self):
        """Test the fields-of-view and fov-locations endpoints

        1. Test creation of a field of view
        2. Test fetching a field of view
        3. Test creation of a field of view location
        4. Test creation of another and usurping default provenance
        5. Test filtering fields of view by brain region
        """
        # test the create endpoint
        url = reverse('fieldsofview-list')
        response = self.post(url, self.dict_fov)
        d = self.ar(response, 201)

        # test the detail endpoint
        response = self.client.get(reverse('fieldsofview-detail', args=[d['id']]))
        d = self.ar(response, 200)
        fov_id = d['id']

        # create fov location
        url = reverse('fovlocation-list')
        loc_dict = {'n_xyz': (512, 512, 1), 'field_of_view': fov_id, 'provenance': 'E',
                    'default_provenance': True, 'coordinate_system': 'IBL-Allen',
                    'brain_region': [53, 348, 9]}
        loc_dict.update(
            {k: [random() + randint(0, 5) * choice([1, -1]) for _ in range(4)] for k in 'xyz'}
        )
        response = self.post(url, loc_dict)
        self.ar(response, 201)

        loc_dict.update(provenance='H', brain_region=[53, 348, 355])
        response = self.post(url, loc_dict)
        self.ar(response, 201)

        # Assert that default provenance changed for previous estimate
        url = reverse('fieldsofview-list')
        response = self.client.get(url)
        fov, = self.ar(response, 200)
        self.assertEqual(2, len(fov['location']))
        provenance = {x['provenance']: x['default_provenance'] for x in fov['location']}
        self.assertDictEqual(provenance, {'E': False, 'H': True})

        # Creating another with the same provenance should return a 500
        url = reverse('fovlocation-list')
        with transaction.atomic():
            response = self.post(url, loc_dict)
            self.ar(response, 500)

        url = reverse('fieldsofview-list')
        # FOV location containing atlas ID 9 should no longer be default provenance and therefore
        # should be excluded from the filter
        r = self.ar(self.client.get(url + '?atlas_acronym=SSp-tr6a'), 200)  # atlas id 9
        self.assertEqual(0, len(r))

        url = reverse('fieldsofview-list')
        r = self.ar(self.client.get(url + '?atlas_acronym=AIp6b'), 200)  # atlas id 355
        self.assertEqual(1, len(r))
        # First location in list should be default provenance = True
        self.assertEqual([True, False], [x['default_provenance'] for x in r[0]['location']])
        self.assertIn(355, r[0]['location'][0]['brain_region'])
