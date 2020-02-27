import csv
import numpy as np

from experiments.models import BrainRegion

csv_file = "/var/www/alyx-dev/alyx/experiments/fixtures/allen_structure_tree.csv"

with open(csv_file, newline='') as fid:
    data = list(csv.reader(fid))

data.pop(0)
id = np.array([int(d[0]) for d in data], dtype='int32')
name = np.array([d[2] for d in data], dtype='object')
acronym = np.array([d[3] for d in data], dtype='object')
parent = np.array([int(d[8] or '0') for d in data], dtype='int32')

for d in data:
    id = int(d[0])
    name = d[2]
    acronym = d[3]
    parent = int(d[8] or '0')
    br, _ = BrainRegion.objects.get_or_create(id=id, name=name, acronym=acronym)
    if parent != br.pk:
        br.parent = BrainRegion.objects.get(id=parent)
        br.save()
