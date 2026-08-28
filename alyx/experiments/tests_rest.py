from random import random, choice, randint

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from alyx.base import BaseTests
from actions.models import Session, ProcedureType
from misc.models import Lab
from subjects.models import Subject, Project
from experiments.models import ProbeInsertion, ImagingType, FOV, ImagingStack
from data.models import Dataset, DatasetType, Tag


class APIProbeExperimentTests(BaseTests):

    fixtures = ['experiments.brainregion.json', 'experiments.probemodel.json']

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.session = Session.objects.first()
        # need to add ephys procedure
        self.session.task_protocol = 'ephys'
        self.session.projects.add(Project.objects.get_or_create(name='brain_wide')[0])
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
        self.assertIn('session_info', d[0])
        # Ensure the session_info includes the projects as a list of names
        self.assertCountEqual(d[0]['session_info'].get('projects', []), ['brain_wide'])

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
        urlf = (reverse('probeinsertion-list') + '?&project=foobar')
        probe_ins = self.ar(self.client.get(urlf))
        self.assertTrue(len(probe_ins) == 0)

        # Test that the serializer returns probes sorted by session start time and then name
        # Create a more recent session
        session = Session.objects.create(subject=self.session.subject, number=2)
        session.task_protocol = 'ephys'
        session.save()
        insertions = []
        for name in ['probe01', 'probe02', 'probe00']:
            insertion = {'session': str(session.id),
                         'name': name,
                         'model': '3A'
                         }
            url = reverse('probeinsertion-list')
            insertions.append(self.ar(self.post(url, insertion), 201))

        probe_ins = self.ar(self.client.get(reverse('probeinsertion-list')), 200)
        self.assertEqual(probe_ins[0]['session_info']['id'], str(session.id))
        self.assertEqual(['probe00', 'probe01', 'probe02', 'probe00', 'probe01'],
                         [x['name'] for x in probe_ins])

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

    def test_chronic_insertion_list_query_count(self):
        """The chronic insertions list costs a fixed number of queries, whatever its length.

        Its nested probe insertions used to be eagerly loaded while serialising each row, which
        discarded the prefetched result and cost two queries per chronic insertion.
        """
        url = reverse('chronicinsertion-list')

        def add_chronic_insertion(i):
            """a chronic insertion with two probe insertions on two sessions"""
            ci = self.ar(self.post(url, {
                'subject': self.session.subject.nickname, 'serial': f'1901910{i}',
                'model': '3B2', 'name': f'probe{i:02}'}), 201)
            for number in range(2):
                session = Session.objects.create(
                    subject=self.session.subject, number=10 * i + number)
                session.projects.add(*self.session.projects.all())
                self.ar(self.post(reverse('probeinsertion-list'), {
                    'session': str(session.id), 'name': f'probe0{number}', 'model': '3B2',
                    'chronic_insertion': ci['id'], 'serial': f'1901910{i}'}), 201)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                r = self.client.get(url + '?limit=250')
            self.assertEqual(200, r.status_code)
            self.assertTrue(all(len(x['probe_insertion']) == 2 for x in r.data['results']))
            return len(ctx.captured_queries), r.data['count']

        add_chronic_insertion(0)
        one, n_one = count_queries()
        self.assertEqual(1, n_one)
        for i in (1, 2, 3):
            add_chronic_insertion(i)
        several, n_several = count_queries()
        self.assertEqual(4, n_several)

        # the point of the eager loading: the same queries serve one row or many
        self.assertEqual(one, several,
                         f'{one} queries for 1 chronic insertion but {several} for 4')

    def test_probe_insertion_tag_filter(self):
        """Insertions are matched via the tags of their datasets, without duplicating rows."""
        tag = Tag.objects.create(name='2020_Q1_Test_et_al')
        other_tag = Tag.objects.create(name='unrelated_tag')
        url = reverse('probeinsertion-list')
        ins = [ProbeInsertion.objects.create(session=self.session, name=f'probe0{i}')
               for i in range(3)]
        # two tagged datasets on the same insertion must not duplicate it in the response
        for name in ('obj.attr.npy', 'obj.times.npy'):
            dset = Dataset.objects.create(session=self.session, name=name)
            dset.tags.add(tag)
            ins[0].datasets.add(dset)
        dset = Dataset.objects.create(session=self.session, name='obj.attr.npy')
        dset.tags.add(tag, other_tag)
        ins[1].datasets.add(dset)
        dset = Dataset.objects.create(session=self.session, name='obj.attr.npy')
        dset.tags.add(other_tag)
        ins[2].datasets.add(dset)
        # a tagged dataset belonging to no insertion must not affect the filter
        Dataset.objects.create(name='aggregate.attr.npy').tags.add(tag)

        expected = sorted([str(ins[0].pk), str(ins[1].pk)])
        d = self.ar(self.client.get(url + f'?tag={tag.name}'))
        self.assertEqual(expected, sorted(x['id'] for x in d))

        # the lookup is a case-insensitive partial match on the tag name
        d = self.ar(self.client.get(url + '?tag=test_ET_al'))
        self.assertEqual(expected, sorted(x['id'] for x in d))

        d = self.ar(self.client.get(url + f'?tag={other_tag.name}'))
        self.assertEqual(sorted([str(ins[1].pk), str(ins[2].pk)]),
                         sorted(x['id'] for x in d))

        d = self.ar(self.client.get(url + '?tag=no_such_tag'))
        self.assertEqual([], d)

        # combining with another many-to-many filter must not duplicate rows either: the
        # project lookup matches both of the session's projects
        self.session.projects.add(Project.objects.get_or_create(name='brain_wide_map')[0])
        d = self.ar(self.client.get(url + f'?tag={tag.name}&project=brain_wide'))
        self.assertEqual(expected, sorted(x['id'] for x in d))

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
                 'chronic_insertion': None,
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
                 'chronic_insertion': None,
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
                     'probe_insertion': None,
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
                                    dataset_type=dtype1, collection='alf/probe_00', qc=30)
        Dataset.objects.create(session=self.session, name='clusters.amps.npy',
                               dataset_type=dtype2, collection='alf/probe_00', qc=40)
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

        # test dataset + qc filters
        q = '?datasets=spikes.times.npy,clusters.amps.npy&dataset_qc_lte=FAIL'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1, 'Expect insertion returned as all dsets match QC')
        q = '?datasets=spikes.times.npy,clusters.amps.npy&dataset_qc_lte=WARNING'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 0, 'Expect none returned as one dset doesn''t match QC')
        q = '?datasets=spikes.times.npy&dataset_qc_lte=30'  # QC code should also work
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1, 'Expect insertion returned as searched dset matches QC')

        # test qc alone
        q = '?dataset_qc_lte=WARNING'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1, 'Expect insertion returned as at least 1 dset matches QC')
        q = '?dataset_qc_lte=10'  # PASS
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 0, 'Expect none returned as no dset matches QC')

        # test filtering by tag
        q = '?tag=tag_test'
        d = self.ar(self.client.get(reverse('probeinsertion-list') + q))
        self.assertEqual(len(d), 1)
        self.assertEqual(probe['id'], d[0]['id'])

    def test_datasets_filter_counts_distinct_names(self):
        """Several datasets sharing one name do not satisfy a request for several names.

        A name routinely matches more than one dataset of an insertion, across collections and
        revisions, so counting the datasets rather than the distinct names let an insertion
        holding two copies of one requested name pass as having two different ones.
        """
        probe = self.ar(self.post(reverse('probeinsertion-list'), self.dict_insertion), 201)
        dtype, _ = DatasetType.objects.get_or_create(name='channels.localCoordinates')
        # two datasets of the same name, as a session has one per probe
        for collection in ('alf/probe_00/pykilosort', 'alf/probe_00/iblsort'):
            Dataset.objects.create(
                session=self.session, name='channels.localCoordinates.npy',
                dataset_type=dtype, collection=collection, qc=30)
        insertion = ProbeInsertion.objects.get(pk=probe['id'])
        self.assertEqual(2, insertion.datasets.count())

        url = reverse('probeinsertion-list')
        # the one name it does have is matched
        d = self.ar(self.client.get(url + '?datasets=channels.localCoordinates.npy'))
        self.assertEqual([probe['id']], [x['id'] for x in d])
        # but it does not have both of these, so it must not be returned
        q = '?datasets=channels.localCoordinates.npy,spikes.times.npy'
        self.assertEqual([], self.ar(self.client.get(url + q)))
        # a name repeated in the query asks for that one dataset, not for two of them
        q = '?datasets=channels.localCoordinates.npy,channels.localCoordinates.npy'
        self.assertEqual([probe['id']], [x['id'] for x in self.ar(self.client.get(url + q))])

    def test_dataset_filters_do_not_duplicate_insertions(self):
        """An insertion is returned once however many of its datasets match the filter.

        Each of these filters used to join the datasets into the insertion query, returning the
        insertion once per matching dataset and reporting the number of (insertion, dataset) pairs
        as the count.
        """
        probe = self.ar(self.post(reverse('probeinsertion-list'), self.dict_insertion), 201)
        dtype, _ = DatasetType.objects.get_or_create(name='spikes.times')
        tag, _ = Tag.objects.get_or_create(name='tag_test')
        # three datasets on the one insertion, all matching every filter below
        for i in range(3):
            dset = Dataset.objects.create(
                session=self.session, name='spikes.times.npy', dataset_type=dtype,
                collection='alf/probe_00', qc=30, revision=None, version=str(i))
            dset.tags.add(tag)
        insertion = ProbeInsertion.objects.get(pk=probe['id'])
        self.assertEqual(3, insertion.datasets.count(), 'expected all three to be associated')

        url = reverse('probeinsertion-list')
        for query in ('?dataset_qc_lte=WARNING', '?dataset_types=spikes.times',
                      '?datasets=spikes.times.npy', '?tag=tag_test'):
            with self.subTest(query=query):
                r = self.client.get(url + query)
                self.assertEqual(200, r.status_code)
                self.assertEqual(1, r.data['count'], 'count must not be a pair count')
                self.assertEqual([probe['id']], [x['id'] for x in r.data['results']])

    def test_atlas_filters_do_not_duplicate_rows(self):
        """A session is returned once however many of its insertions are in the brain region.

        The session branch of the brain region filter ORs two joins together with no DISTINCT, so
        a session came back once per insertion recording the region -- which is most of them, as
        sessions routinely have two probes.
        """
        insertions = []
        for name in ('probe00', 'probe01'):
            insertion = self.ar(self.post(reverse('probeinsertion-list'),
                                          dict(self.dict_insertion, name=name)), 201)
            insertions.append(insertion['id'])
            # only one trajectory per provenance is allowed per insertion, and only the ephys
            # aligned provenance (70) is considered by the filter
            traj = self.ar(self.post(reverse('trajectoryestimate-list'), {
                'probe_insertion': insertion['id'], 'x': -4521.2, 'y': 2415.0, 'z': 0,
                'phi': 80, 'theta': 10, 'depth': 5000, 'roll': 0,
                'provenance': 'Ephys aligned histology track'}), 201)
            for axial in (20, 40, 60):
                self.ar(self.post(reverse('channel-list'), {
                    'x': 111.1, 'y': -222.2, 'z': 333.3, 'axial': axial, 'lateral': 40,
                    'brain_region': 593,  # VISp1
                    'trajectory_estimate': traj['id']}), 201)

        for query in ('?atlas_acronym=VISp1', '?atlas_id=593', '?atlas_name=primary visual'):
            with self.subTest(query=query):
                r = self.client.get(reverse('session-list') + query)
                self.assertEqual(200, r.status_code)
                self.assertEqual(1, r.data['count'],
                                 'the session must not be returned once per insertion')
                self.assertEqual([str(self.session.pk)], [x['id'] for x in r.data['results']])
                # both insertions are in the region, and each is returned exactly once
                r = self.client.get(reverse('probeinsertion-list') + query)
                self.assertEqual(200, r.status_code)
                self.assertEqual(2, r.data['count'])
                self.assertEqual(sorted(insertions), sorted(x['id'] for x in r.data['results']))


class APIImagingExperimentTests(BaseTests):
    fixtures = ['experiments.brainregion.json', 'experiments.coordinatesystem.json']

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        # self.session = Session.objects.first()
        lab = Lab.objects.create(name='lab')
        subject = Subject.objects.create(nickname='586', lab=lab)
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
            self.assertIn(response.status_code, (400, 500))  # In later versions status code is 400

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

    def test_imaging_stack_list_one_row_per_stack(self):
        """A stack is listed once however many slices it holds.

        The list was ordered by `slices__name`, which joined the slices into the query and returned
        the stack once per slice while the reported count stayed at the number of stacks.
        """
        stack = ImagingStack.objects.create(name='stack_00')
        url = reverse('fieldsofview-list')
        for name in ('FOV_02', 'FOV_00', 'FOV_01'):
            fov = self.ar(self.post(url, dict(self.dict_fov, name=name)), 201)
            # not queryset.update(): BaseQuerySet.update sets auto_datetime, which FOV lacks
            obj = FOV.objects.get(pk=fov['id'])
            obj.stack = stack
            obj.save()
        self.assertEqual(3, stack.slices.count())

        r = self.client.get(reverse('imagingstack-list') + '?limit=250')
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, r.data['count'])
        self.assertEqual(1, len(r.data['results']), 'the stack must not repeat per slice')
        # and its slices are ordered by name rather than however they were created
        slices = r.data['results'][0]['slices']
        self.assertEqual(['FOV_00', 'FOV_01', 'FOV_02'], [s['name'] for s in slices])

    def test_session_list_ordering_uses_number(self):
        """Sessions sharing a start time are ordered by number, not by whatever the database picks.

        Session declares no uniqueness, and 916 of them share a start time with another, so the
        sort key needs more than the start time to place them.
        """
        start = now()
        subject = self.session.subject
        created = [Session.objects.create(subject=subject, start_time=start, number=n)
                   for n in (3, 1, 2)]
        r = self.client.get(reverse('session-list') + f'?subject={subject.nickname}&limit=250')
        rows = [x for x in self.ar(r) if x['id'] in {str(s.pk) for s in created}]
        self.assertEqual([1, 2, 3], [x['number'] for x in rows])

    def test_fov_dataset_qc_filter(self):
        """FOVs are matched on the QC of their datasets, as sessions and insertions are."""
        # the datasets must exist before the fields of view: the FOV post_save signal is what
        # associates them, by matching the FOV name against the dataset collection
        dtype, _ = DatasetType.objects.get_or_create(name='obj.attr')
        for fov_name, name, qc in (('FOV_00', 'obj.attr.npy', 10),    # PASS
                                   ('FOV_00', 'obj.times.npy', 10),   # a second qualifying dset
                                   ('FOV_01', 'obj.attr.npy', 40),    # FAIL
                                   ('FOV_02', 'obj.attr.npy', 50)):   # CRITICAL
            Dataset.objects.create(session=self.session, name=name, dataset_type=dtype,
                                   collection=f'alf/{fov_name}', qc=qc)
        url = reverse('fieldsofview-list')
        fovs = {}
        for name in ('FOV_00', 'FOV_01', 'FOV_02'):
            fovs[name] = self.ar(self.post(url, dict(self.dict_fov, name=name)), 201)['id']

        # FOV_00 has two datasets at PASS and must still be returned exactly once
        r = self.client.get(url + '?dataset_qc_lte=PASS')
        self.assertEqual(1, r.data['count'])
        self.assertEqual([fovs['FOV_00']], [x['id'] for x in r.data['results']])

        r = self.client.get(url + '?dataset_qc_lte=FAIL')
        self.assertEqual(sorted([fovs['FOV_00'], fovs['FOV_01']]),
                         sorted(x['id'] for x in self.ar(r)))

        # a QC code should work as well as a name, as on the other endpoints
        d = self.ar(self.client.get(url + '?dataset_qc_lte=10'))
        self.assertEqual([fovs['FOV_00']], [x['id'] for x in d])

        # combined with datasets, the datasets filter applies the QC bound to the named dataset
        d = self.ar(self.client.get(url + '?datasets=obj.attr.npy&dataset_qc_lte=PASS'))
        self.assertEqual([fovs['FOV_00']], [x['id'] for x in d])
        d = self.ar(self.client.get(url + '?datasets=obj.attr.npy&dataset_qc_lte=FAIL'))
        self.assertEqual(sorted([fovs['FOV_00'], fovs['FOV_01']]),
                         sorted(x['id'] for x in d))
        # obj.times.npy is only on FOV_00, and only at PASS
        d = self.ar(self.client.get(url + '?datasets=obj.attr.npy,obj.times.npy'))
        self.assertEqual([fovs['FOV_00']], [x['id'] for x in d])

    def test_fov_tag_filter(self):
        """FOVs are matched via the tags of their datasets, without duplicating rows."""
        tag = Tag.objects.create(name='2020_Q1_Test_et_al')
        other_tag = Tag.objects.create(name='unrelated_tag')
        # the datasets must exist before the fields of view: the FOV post_save signal is what
        # associates them, by matching the FOV name against the dataset collection
        dsets = {
            ('FOV_00', 'obj.attr.npy'): [tag],
            ('FOV_00', 'obj.times.npy'): [tag],  # two tagged datasets on one FOV
            ('FOV_01', 'obj.attr.npy'): [tag, other_tag],
            ('FOV_02', 'obj.attr.npy'): [other_tag],
        }
        for (fov_name, dset_name), tags in dsets.items():
            dset = Dataset.objects.create(
                session=self.session, name=dset_name, collection=f'alf/{fov_name}')
            dset.tags.add(*tags)
        # a tagged dataset belonging to no field of view must not affect the filter
        Dataset.objects.create(name='aggregate.attr.npy').tags.add(tag)

        url = reverse('fieldsofview-list')
        fovs = {}
        for name in ('FOV_00', 'FOV_01', 'FOV_02'):
            d = self.ar(self.post(url, dict(self.dict_fov, name=name)), 201)
            fovs[name] = d['id']
        # the signal should have associated the datasets with their field of view
        self.assertEqual(2, len(FOV.objects.get(pk=fovs['FOV_00']).datasets.all()))

        expected = sorted([fovs['FOV_00'], fovs['FOV_01']])
        r = self.ar(self.client.get(url + f'?tag={tag.name}'), 200)
        self.assertEqual(expected, sorted(x['id'] for x in r))

        # the lookup is a case-insensitive partial match on the tag name
        r = self.ar(self.client.get(url + '?tag=test_ET_al'), 200)
        self.assertEqual(expected, sorted(x['id'] for x in r))

        r = self.ar(self.client.get(url + f'?tag={other_tag.name}'), 200)
        self.assertEqual(sorted([fovs['FOV_01'], fovs['FOV_02']]),
                         sorted(x['id'] for x in r))

        r = self.ar(self.client.get(url + '?tag=no_such_tag'), 200)
        self.assertEqual([], r)
