from collections import defaultdict
import os.path as op
import json
import sys

if len(sys.argv) <= 1:
    exit()
fn = sys.argv[1]
with open(fn, 'r') as f:
    data = json.load(f)

N_MAX = 50
LIMIT_MODELS = ('actions.wateradministration',
                'actions.weighing',
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
    # Increment model counter.
    counter[item['model']] += 1
    data_out.append(item)
# Output file.
bn, ext = op.splitext(fn)
fn_out = bn + '_anon' + ext
with open(fn_out, 'w') as f:
    json.dump(data_out, f, indent=1, sort_keys=True)
