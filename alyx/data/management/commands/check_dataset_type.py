import logging

from one.registration import get_dataset_type, Bunch

from django.core.management import BaseCommand

from data.models import Dataset, DatasetType
logging.getLogger(__name__).setLevel(logging.WARNING)


class Command(BaseCommand):
    """
        ./manage.py check_dataset_type --pattern '_*_object.attribute.*'
        ./manage.py check_dataset_type --pattern '_*_object.attribute.*' --filename '_m1_object.attribute.json'
        ./manage.py check_dataset_type --name 'object.attribute' --filename '_m1_object.attribute.json'
        ./manage.py check_dataset_type --pattern '_*_object.attribute.*' --strict
    """
    help = "Check dataset type patterns against existing datasets."

    def add_arguments(self, parser):
        parser.add_argument('--name', help='Dataset type name', default='__new_dataset_type__')
        parser.add_argument('--pattern', help='Pattern to match dataset types', type=str)
        parser.add_argument('--filename', help='A filename that should match the pattern')
        parser.add_argument(
            '--strict', help='Whether to check other dataset types strictly', action='store_true')

    def handle(self, *args, **options):
        name = options.get('name')
        pattern = options.get('pattern')
        filename = options.get('filename')
        # Fetch one dataset for each dataset type
        self.stdout.write('Fetching one dataset for each dataset type...')
        dsets = (
            Dataset.objects
            .order_by('dataset_type', '-auto_datetime')
            .distinct('dataset_type')
            .values_list('name', 'dataset_type')
        )
        dtypes = list(map(Bunch, DatasetType.objects.values('id', 'name', 'filename_pattern')))
        assert name not in [d['name'] for d in dtypes], \
            f'Dataset type name {name} already exists.'
        assert pattern not in [d['filename_pattern'] for d in dtypes], \
            f'Pattern {pattern} already exists.'
        dtypes.append(Bunch({'id': name, 'name': name, 'filename_pattern': pattern}))
        # If example filename provided, check it against all patterns
        if filename:
            self.stdout.write(f'Checking filename "{filename}" against all patterns...')
            dtype = get_dataset_type(filename, dtypes)
            assert dtype == dtypes[-1], (
                f'Filename "{filename}" did not match the expected pattern "{pattern}". '
                f'Got dataset type: {dtype}'
            )

        # Check dataset types for existing datasets
        for dset, expected_dtype in dsets:
            try:
                dtype = get_dataset_type(dset, dtypes)
            except ValueError as e:
                if not options.get('strict') and 'No dataset type found' in str(e):
                    dtype = DatasetType.objects.get(id=expected_dtype)
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping dataset "{dset}" as no matching dataset type found '
                            f'(expected {dtype.name} {expected_dtype}).'
                        )
                    )
                    continue
                else:
                    raise
            assert dtype['id'] == expected_dtype, (
                f'Dataset type mismatch for dataset: {dset}. '
                f'Expected: {expected_dtype}, Found: {dtype["id"]}'
            )

        self.stdout.write(self.style.SUCCESS('All dataset type patterns appear valid.'))
