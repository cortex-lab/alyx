"""Move implant weight in test fixtures."""
import gzip
import json
import random
from pathlib import Path

# Fixture file
path = Path(__file__).parents[2].joinpath('data', 'all_dumped_anon.json.gz')
if not path.exists():
    raise FileNotFoundError

# Load and parse fixture
with gzip.open(path, 'rb') as fp:
    data = json.load(fp)

# Get implant weight map
pk2iw = {r['pk']: r['fields']['implant_weight']
         for r in filter(lambda r: r['model'] == 'subjects.subject', data)}

# Add implant weights to surgeries
for record in filter(lambda r: r['model'] == 'actions.surgery', data):
    # Check if implant surgery
    implant = (any('implant' in p for p in record['fields'].get('procedures', [])) or
               'headplate' in record['fields']['narrative'])
    # Implant weight should be subject's implant weight
    iw = pk2iw[record['fields']['subject']]
    if iw is None:  # ... or a random float rounded to 2 decimal places
        iw = float(f'{random.randint(15, 20) + random.random():.2f}')
    # If not implant surgery, set to 0, otherwise use above weight
    record['fields'].update(implant_weight=iw if implant else 0.)

# Remove implant weights from subjects
for record in filter(lambda r: r['model'] == 'subjects.subject', data):
    record['fields'].pop('implant_weight')

# find any with multiple surgeries
# from collections import Counter
# surgeries = filter(lambda r: r['model'] == 'actions.surgery', data)
# counter = Counter(map(lambda r: r['fields']['subject'], surgeries))
# pk, total = counter.most_common()[3]
# assert total > 1
# recs = filter(lambda r: r['model'] == 'actions.surgery' and r['fields']['subject'] == pk, data)

# Write to file
with gzip.open(path, 'wt', encoding='UTF-8') as fp:
    json.dump(data, fp, indent=2)
