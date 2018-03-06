from django.core.management import BaseCommand

from data import globus
from data.models import Dataset


def _iter_datasets(dataset_id=None, limit=None, user=None):
    dataset_ids = [dataset_id] if dataset_id is not None else globus._incomplete_dataset_ids()
    datasets = Dataset.objects.filter(pk__in=dataset_ids).order_by('-created_datetime')
    if user is not None:
        datasets = datasets.filter(created_by__username=user)
    if limit is not None:
        datasets = datasets[:int(limit)]
    for dataset in datasets:
        yield dataset


class Command(BaseCommand):
    help = "Interact with globus"

    def add_arguments(self, parser):
        parser.add_argument('action', help='Action')
        parser.add_argument('dataset', nargs='?', help='Dataset')
        parser.add_argument('--dry', action='store_true', help='dry run')
        parser.add_argument('--limit', help='limit to a maximum number of datasets')
        parser.add_argument('--user', help='select datasets created by a given user')

    def handle(self, *args, **options):
        action = options.get('action')
        dataset_id = options.get('dataset')
        limit = options.get('limit')
        user = options.get('user')
        dry = options.get('dry')

        if action == 'login':
            globus.create_globus_token()
            self.stdout.write(self.style.SUCCESS("Login successful."))

        if action == 'sync':
            for dataset in _iter_datasets(dataset_id, limit=limit, user=user):
                self.stdout.write("Synchronizing file status of %s" % str(dataset))
                if not dry:
                    globus.update_file_exists(dataset)

        if action == 'transfer':
            for dataset in _iter_datasets(dataset_id, limit=limit, user=user):
                transfers = globus.transfers_required(dataset)
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
