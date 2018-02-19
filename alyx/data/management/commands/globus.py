import json

from django.core.management import BaseCommand

from data import globus
from data.models import Dataset


class Command(BaseCommand):
    help = "Interact with globus"

    def add_arguments(self, parser):
        parser.add_argument('action', help='Action')
        parser.add_argument('dataset', nargs='?', help='Dataset')
        parser.add_argument('--dry', action='store_true')

    def handle(self, *args, **options):
        action = options.get('action')
        dataset = options.get('dataset')
        dry = options.get('dry')

        if action == 'login':
            globus.create_globus_token()
            self.stdout.write(self.style.SUCCESS("Login successful."))

        if action == 'sync' and dataset:
            globus.update_file_exists(Dataset.objects.get(pk=dataset))

        if action == 'transfer' and dataset:
            transfers = globus.transfers_required(Dataset.objects.get(pk=dataset))
            for transfer in transfers:
                self.stdout.write(
                    "Launch Globus transfer from %s:%s to %s:%s." % (
                        transfer['source_data_repository'],
                        transfer['source_path'],
                        transfer['destination_data_repository'],
                        transfer['destination_path'],
                    )
                )
                if not dry:
                    globus.start_globus_transfer(
                        transfer['source_file_record'], transfer['destination_file_record'])
