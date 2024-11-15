from datetime import date

from django.core.management import BaseCommand

from jobs.models import Task


class Command(BaseCommand):
    """
        ./manage.py tasks cleanup --before 2020-01-01 --status=20 --dry
        ./manage.py tasks cleanup --status=Waiting --dry
        ./manage.py tasks cleanup --status=~Complete --limit=200
    """
    help = 'Manage tasks'

    def add_arguments(self, parser):
        parser.add_argument('action', help='Action')
        parser.add_argument('--status', help='Only delete tasks with this status')
        parser.add_argument('--dry', action='store_true', help='dry run')
        parser.add_argument('--limit', help='limit to a maximum number of tasks')
        parser.add_argument('--before', help='select tasks before a given date')
        parser.add_argument('--signed-off', action='store_true',
                            help='select tasks associated with signed-off sessions')

    def handle(self, *args, **options):
        action = options.get('action')

        dry = options.get('dry')
        before = options.get('before', date.today().isoformat())

        if action != 'cleanup':
            raise ValueError(f'Action "{action}" not recognized')

        before = date.fromisoformat(before)  # validate
        tasks = Task.objects.filter(datetime__date__lte=before)
        # Filter status
        if status := options.get('status'):
            if status.startswith('~'):
                status = status[1:]
                fcn = tasks.exclude
            else:
                fcn = tasks.filter
            if status.isnumeric():
                status = int(status)
                if status not in {s[0] for s in Task.STATUS_DATA_SOURCES}:
                    raise ValueError(f'Status {status} not recognized')
            else:  # convert status string to int
                status = next(
                    (i for i, s in Task.STATUS_DATA_SOURCES if s.casefold() == status.casefold()),
                    None
                )
                if status is None:
                    raise ValueError(f'Status "{status}" not recognized')
            tasks = fcn(status=status)

        # Filter signed-off
        if options.get('signed_off'):
            tasks = tasks.filter(session__json__sign_off_checklist__sign_off_date__isnull=False)

        # Limit
        if (limit := options.get('limit')) is not None:
            limit = int(limit)
            tasks = tasks.order_by('datetime')[:limit]

        self.stdout.write(self.style.SUCCESS(f'Found {tasks.count()} tasks to delete'))
        if not dry:
            if limit is None:
                tasks.delete()
            else:
                pks = tasks.values_list('pk', flat=True)
                Task.objects.filter(pk__in=pks).delete()
            self.stdout.write(self.style.SUCCESS('Tasks deleted'))
