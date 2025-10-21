from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import datetime, timedelta

from actions.models import Session
from alyx.base import BaseTests
from data.models import DataRepository
from jobs.management.commands import tasks
from jobs.models import Task
from subjects.models import Subject
from misc.models import Lab


class APISubjectsTests(BaseTests):
    fixtures = ['experiments.probemodel.json', 'experiments.brainregion.json']

    def setUp(self):
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


class TestManagementTasks(BaseTests):
    """Tests for the tasks management command."""

    def setUp(self) -> None:
        """Create some tasks to clean up."""
        self.n_tasks = 100
        self.command = tasks.Command()
        self.base = datetime(2024, 1, 1)
        # Create equally-spaced task dates
        date_list = [self.base - timedelta(days=x) for x in range(self.n_tasks)]
        with patch('django.db.models.fields.timezone.now') as timezone_mock:
            for i, date in enumerate(date_list):
                timezone_mock.return_value = date
                status = Task.STATUS_DATA_SOURCES[i % len(Task.STATUS_DATA_SOURCES)][0]
                Task.objects.create(name=f'task_{i}', status=status)
        # Create a session for testing signed-off filter
        lab = Lab.objects.create(name='lab')
        subject = Subject.objects.create(nickname='586', lab=lab)
        json_data = {'sign_off_checklist': {'sign_off_date': self.base.isoformat()}}
        self.session = Session.objects.create(
            subject=subject, number=1, json=json_data, type='Experiment')
        t = Task.objects.first()
        t.session = self.session
        t.save()

    def test_cleanup(self):
        """Test for cleanup action."""
        # First run in dry mode, expect submit_delete to not be called
        n = self.n_tasks - 10
        before_date = (self.base - timedelta(days=n - .1)).date()
        with patch.object(self.command.stdout, 'write') as stdout_mock:
            self.command.handle(action='cleanup', before=str(before_date), dry=True)
            stdout_mock.assert_called()
            self.assertIn(f'Found {10} tasks to delete', stdout_mock.call_args.args[0])
        # All tasks should still exist
        self.assertEqual(self.n_tasks, Task.objects.count())

        # Without dry flag, tasks should be removed
        self.command.handle(action='cleanup', before=str(before_date))
        # All tasks should still exist
        self.assertEqual(n, Task.objects.count())
        self.assertEqual(0, Task.objects.filter(datetime__date__lte=before_date).count())

        # With signed-off filter
        assert (n := self.session.tasks.count()) > 0
        self.command.handle(action='cleanup', signed_off=True)
        self.assertEqual(0, self.session.tasks.count())

        # With status filter as int
        n = Task.objects.count() - Task.objects.filter(status=20).count()
        self.command.handle(action='cleanup', status='20')
        self.assertEqual(n, Task.objects.count())
        self.assertEqual(0, Task.objects.filter(status=20).count())

        # With status filter as string
        n = Task.objects.count() - Task.objects.filter(status=40).count()
        self.command.handle(action='cleanup', status='Errored')
        self.assertEqual(n, Task.objects.count())
        self.assertEqual(0, Task.objects.filter(status=40).count())

        # With status filter as string and ~
        n_days = self.n_tasks - 20
        before_date = (self.base - timedelta(days=n_days)).date()
        n = Task.objects.count()
        n -= Task.objects.exclude(status=45).filter(datetime__date__lte=before_date).count()
        self.command.handle(action='cleanup', status='~Abandoned', before=str(before_date))
        self.assertEqual(n, Task.objects.count())
        n_tasks = Task.objects.exclude(status=45).filter(datetime__date__lte=before_date).count()
        self.assertEqual(0, n_tasks)
        self.assertTrue(Task.objects.filter(status=45, datetime__date__lte=before_date).count())

        # With status filter as int and ~ with limit
        n = Task.objects.exclude(status=60).count() - 5
        self.command.handle(action='cleanup', status='~60', limit='5')
        self.assertEqual(n, Task.objects.exclude(status=60).count())

        # Error handling
        self.assertRaises(ValueError, self.command.handle, action='cleanup', status='NotAStatus')
        self.assertRaises(ValueError, self.command.handle, action='cleanup', status='1000')
        self.assertRaises(ValueError, self.command.handle, action='NotAnAction')
