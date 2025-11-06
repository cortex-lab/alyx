from django.core.management import BaseCommand
from django.utils import timezone
from actions.models import Notification


class Command(BaseCommand):
    help = "Delete old or expired notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            '--n-days-old', type=int, default=30,
            help='Only delete notifications where send_at is older than n days')
        parser.add_argument(
            '--status', help='Only delete notifications with this status', type=str, default=None)
        parser.add_argument(
            '--dry-run', help='Simulate deletion without actually deleting', action='store_true')

    def handle(self, *args, **options):
        n_days_old = options['n_days_old']
        status = options['status']
        cutoff_date = timezone.now() - timezone.timedelta(days=n_days_old)

        notifications = Notification.objects.filter(send_at__lt=cutoff_date)

        if status:
            notifications = notifications.filter(status=status)

        if options['dry_run']:
            message = f'Dry run: {notifications.count()} notifications found'
            if status:
                message += f' with status "{status}"'
            self.stdout.write(self.style.NOTICE(message))
        else:
            _, deleted_count = notifications.delete()
            message = f'Deleted {deleted_count["actions.Notification"]} notifications'
            if status:
                message += f' with status "{status}"'
            self.stdout.write(self.style.SUCCESS(message))
