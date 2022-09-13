from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command

from actions.models import Session
from alyx.base import BaseTests
from data.models import DataRepository


class APISubjectsTests(BaseTests):

    def setUp(self):
        call_command('loaddata', 'experiments/fixtures/experiments.probemodel.json', verbosity=0)
        call_command('loaddata', 'experiments/fixtures/experiments.brainregion.json', verbosity=0)
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.session = Session.objects.first()
        self.session.task_protocol = 'ephys'
        self.session.save()
        self.dict_insertion = {'session': str(self.session.id),
                               'name': 'probe_00',
                               'model': '3A'}
        self.data_repository = DataRepository.objects.create(name='myrepo')

    def test_brain_regions_rest_filter(self):
        # test the custom filters get_descendants and get_ancestors
        task_dict = {'executable': 'exec', 'priority': 90,
                     'io_charge': 40, 'gpu': 0, 'cpu': 1,
                     'ram': 40, 'module': 'mod', 'parents': [],
                     'level': 0, 'time_out_sec': 2, 'session': self.session.id,
                     'status': 'Waiting', 'log': None, 'name': 'mytask', 'graph': 'mygraph',
                     'arguments': {'titi': 'toto', 'tata': 'tutu'}, 'data_repository': 'myrepo'}
        rep = self.post(reverse('tasks-list'), task_dict)
        self.assertEqual(rep.status_code, 201)
