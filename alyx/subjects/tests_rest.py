from django.contrib.auth import get_user_model
from django.urls import reverse
from alyx.base import BaseTests
from actions.models import WaterAdministration, Weighing
from subjects.models import Subject, Project
from misc.models import Lab


class APISubjectsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.lab = Lab.objects.create(name='awesome_lab')
        self.project = Project.objects.create(name='my_proj')

    def test_list_subjects(self):
        url = reverse('subject-list')
        d = self.ar(self.client.get(url, data={'limit': 300}))
        self.assertTrue(len(d) > 200)
        self.assertTrue({'nickname', 'id', 'responsible_user', 'death_date',
                         'line', 'litter', 'sex', 'genotype', 'url'} <= set(d[0]))

    def test_list_alive_subjects(self):
        url = reverse('subject-list') + '?alive=True&stock=True&limit=300'
        d = self.ar(self.client.get(url))
        self.assertTrue(len(d) > 200)
        self.assertTrue({'nickname', 'id', 'responsible_user', 'death_date'} <= set(d[0]))

        # also test that you can get some back when asking for non-stock
        url = reverse('subject-list') + '?alive=True&stock=False'
        d = self.ar(self.client.get(url))
        self.assertTrue(len(d) > 0)
        self.assertTrue({'nickname', 'id', 'responsible_user', 'death_date'} <= set(d[0]))

    def test_subject_1(self):
        # test the individual subject endpoint, i.e. when you ask for a subject by name
        url = reverse('subject-list')
        response = self.client.get(url)
        d = self.ar(response)

        # Ask for the first subject
        response = self.client.get(d[0]['url'])
        d = self.ar(response)

        expected = {'nickname', 'id', 'responsible_user', 'death_date', 'line', 'litter', 'sex',
                    'genotype', 'url', 'expected_water', 'remaining_water', 'weighings',
                    'projects', 'water_administrations'}
        self.assertTrue(expected <= set(d))

    def test_list_projects(self):
        url = reverse('project-list')
        self.client.post(url, {'name': 'test_project'})
        response = self.client.get(url)
        d = self.ar(response)
        self.assertTrue('test_project' in [p['name'] for p in d])

    def test_subject_water_administration(self):
        subject = WaterAdministration.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        d = self.ar(response)

        self.assertTrue('water_administrations' in d)
        self.assertTrue(d['water_administrations'])
        wa = set(d['water_administrations'][0])
        self.assertTrue({'date_time', 'water_administered', 'water_type', 'url'} <= wa)

    def test_subject_weighing(self):
        subject = Weighing.objects.first().subject
        url = reverse('subject-detail', kwargs={'nickname': subject.nickname})
        response = self.client.get(url)
        d = self.ar(response)

        self.assertTrue('weighings' in d)
        self.assertTrue(d['weighings'])
        w = set(d['weighings'][0])
        self.assertTrue({'date_time', 'weight', 'url'} <= w)

    def test_subject_filters_lab(self):
        # test subjects lab filter
        sub = Subject.objects.first()
        sub.lab = self.lab
        sub.save()
        url = reverse('subject-list') + '?lab=' + self.lab.name
        d = self.ar(self.client.get(url))
        self.assertTrue(len(d) == 1)
        self.assertEqual(d[0]['id'], str(sub.pk))

    def test_subject_filters_project(self):
        # test subjects lab filter
        sub = Subject.objects.all()[1]
        sub.projects.set([self.project])
        sub.save()
        url = reverse('subject-list') + '?project=' + self.project.name
        d = self.ar(self.client.get(url))
        self.assertTrue(len(d) == 1)
        self.assertEqual(d[0]['id'], str(sub.pk))

    def test_subject_filters_water_restriction(self):
        #  makes sure the endpoint only returns alive subjects
        url = reverse('subject-list') + '?water_restricted=True'
        swr = self.ar(self.client.get(url))
        self.assertTrue(all(d['alive'] for d in swr))
        url = reverse('subject-list') + '?water_restricted=False'
        non_swr = self.ar(self.client.get(url))
        self.assertTrue(all(d['alive'] for d in non_swr))
        # paranoid: query dead subjects, alive subjects and make sure all wr subjects are
        # within the alive set but excluded from the dead set
        url = reverse('subject-list') + '?alive=False&limit=1000'
        dead = self.ar(self.client.get(url))
        url = reverse('subject-list') + '?alive=True&limit=1000'
        alive = self.ar(self.client.get(url))
        id_alive = set(d['id'] for d in alive)
        id_dead = set(d['id'] for d in dead)
        id_swr = set(d['id'] for d in swr)
        id_nonswr = set(d['id'] for d in non_swr)
        self.assertEqual(id_swr.intersection(id_alive), id_swr)
        self.assertTrue(len(id_swr.intersection(id_dead)) == 0)
        self.assertEqual(id_nonswr.intersection(id_alive), id_nonswr)
        self.assertTrue(len(id_nonswr.intersection(id_dead)) == 0)

    def test_subject_restricted(self):
        url = reverse('water-restricted-subject-list')
        response = self.client.get(url)
        d = self.ar(response)
        self.assertTrue({'nickname', 'expected_water', 'remaining_water'} <= set(d[0]))


class APIDuplicateNicknameTests(BaseTests):
    """Subjects in different labs may share a nickname."""

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.labs = [Lab.objects.create(name=f'lab_{i}') for i in range(2)]
        # Responsible user is null as nickname and responsible user must also be unique together
        self.subjects = [Subject.objects.create(nickname='dup_001', lab=lab, responsible_user=None)
                         for lab in self.labs]

    def test_get_by_nickname(self):
        Subject.objects.create(nickname='unique_001', lab=self.labs[0])
        self.assertEqual('unique_001', Subject.objects.get_by_nickname('unique_001').nickname)
        # The lab is only used to resolve duplicates
        self.assertEqual(
            'unique_001', Subject.objects.get_by_nickname('unique_001', labs='lab_1').nickname)
        self.assertEqual(self.subjects[1], Subject.objects.get_by_nickname('dup_001', 'lab_1'))
        self.assertEqual(
            self.subjects[0], Subject.objects.get_by_nickname('dup_001', ['foo', 'lab_0']))
        with self.assertRaisesRegex(Subject.MultipleObjectsReturned, 'lab_0, lab_1'):
            Subject.objects.get_by_nickname('dup_001')
        with self.assertRaises(Subject.DoesNotExist):
            Subject.objects.get_by_nickname('foo')

    def test_subject_detail(self):
        url = reverse('subject-detail', kwargs={'nickname': 'dup_001'})
        r = self.client.get(url)
        self.ar(r, 409)
        self.assertIn('specify lab', r.data['detail'])
        d = self.ar(self.client.get(url, data={'lab': 'lab_1'}))
        self.assertEqual(str(self.subjects[1].id), d['id'])
        self.ar(self.client.get(url, data={'lab': 'foo'}), 409)
        # Lookup by UUID
        url = reverse('subject-detail', kwargs={'nickname': str(self.subjects[0].id)})
        self.assertEqual(str(self.subjects[0].id), self.ar(self.client.get(url))['id'])
        url = reverse('subject-detail', kwargs={'nickname': 'foo'})
        self.ar(self.client.get(url), 404)

    def test_create_weighing(self):
        url = reverse('weighing-create')
        data = {'subject': 'dup_001', 'weight': 20.0, 'date_time': '2025-01-01T12:00:00'}
        r = self.post(url, data)
        self.ar(r, 400)
        self.assertIn('specify lab', str(r.data['subject']))
        self.ar(self.post(url, {**data, 'lab': 'lab_1'}), 201)
        self.assertEqual(1, Weighing.objects.filter(subject=self.subjects[1]).count())
        self.assertFalse(Weighing.objects.filter(subject=self.subjects[0]).exists())
