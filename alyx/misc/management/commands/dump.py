from collections import defaultdict
import gzip
import json
import logging
import os
import os.path as op
import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


def _dump_all(path):
    call_command('dumpdata',
                 '-e', 'contenttypes',
                 '-e', 'auth.permission',
                 '-e', 'admin.logentry',
                 '-e', 'authtoken',
                 '-e', 'reversion',
                 '--indent', '1', '-o', path)


def _dump_static(path):
    call_command('dumpdata',
                 '-e', 'contenttypes',
                 'auth.user',
                 'subjects.species',
                 'subjects.source',
                 'equipment.lablocation',
                 'actions.proceduretype',
                 '--indent', '1', '-o', path)


def _anonymize(path):
    """Anonymize a JSON dump so that it can be uploaded publicly on GitHub to be used by CI."""
    with open(path, 'r') as f:
        data = json.load(f)

    N_MAX = 50
    LIMIT_MODELS = ('actions.wateradministration',
                    'actions.weighing',
                    'subjects.session',
                    'subjects.surgery',
                    'subjects.zygosity',
                    'subjects.genotypetest',
                    )

    counter = defaultdict(int)
    data_out = []
    for item in data:
        # Max number of items per model.
        if item['model'] in LIMIT_MODELS and counter[item['model']] >= N_MAX:
            continue
        pk = item['pk']
        # Remove user password and email.
        if item['model'] == 'auth.user':
            item['fields']['password'] = ''
            item['fields']['email'] = ''
        # Remove names.
        for field, value in item['fields'].items():
            if field.endswith('name'):
                item['fields'][field] = pk[:6] if isinstance(pk, str) else str(pk)
            # Remote notes and description.
            if field in ('notes', 'description'):
                item['fields'][field] = '-'
            if field == 'user_permissions':
                item['fields'][field] = []
        # Increment model counter.
        counter[item['model']] += 1
        data_out.append(item)
    # Output file.
    bn, ext = op.splitext(path)
    fn_out = bn + '_anon' + ext
    with open(fn_out, 'w') as f:
        json.dump(data_out, f, indent=1, sort_keys=True)
    return fn_out


def _gzip(path):
    with open(path, 'rb') as f_in, open(path + '.gz', 'wb') as f_out:
        f_out.write(gzip.compress(f_in.read()))


class Command(BaseCommand):
    help = "Dump the entire database"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--output-path', '-o', nargs=1, type=str)
        parser.add_argument('--test', action='store_true', default=False)
        parser.add_argument('--static', action='store_true', default=False)

    def handle(self, *args, **options):
        cur_dir = op.realpath(op.dirname(__file__))
        output_path = options.get('output_path') or ['dump.json']
        output_path = op.abspath(output_path[0])
        output_dir = op.dirname(output_path)
        if not op.exists(output_dir):
            os.makedirs(output_dir)
        if not op.isdir(output_dir):
            self.stdout.write('Error: %s is not a directory' % output_dir)
            return

        # Anonymize the dump, used for tests.
        if options.get('test', None):
            output_path = op.join(cur_dir, '../../../../data/all_dumped.json')
            _dump_all(output_path)
            # Anonymize and gzip.
            _gzip(_anonymize(output_path))

        # Dump just static information.
        elif options.get('static', None):
            output_path = op.join(cur_dir, '../../../../data/json/00-dumped-static.json')
            _dump_static(output_path)

        elif output_path:
            # Make the dump.
            _dump_all(output_path)
