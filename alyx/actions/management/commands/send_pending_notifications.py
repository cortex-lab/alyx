from django.core.management import BaseCommand
from actions.models import send_pending_emails


class Command(BaseCommand):
    help = "Send pending notifications."

    def handle(self, *args, **options):
        send_pending_emails()
