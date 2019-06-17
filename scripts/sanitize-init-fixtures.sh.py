import json

# for the data.datasettype fixture, remove unknown and null the created-by field
file_fixtures = './data/fixtures/data.datasettype.json'
with open(file_fixtures) as ff:
    fix = json.load(ff)

for i, f in enumerate(fix):
    f['fields']['created_by'] = None
    if f['fields']['name'] == 'unknown':
        fix.remove(f)

with open(file_fixtures, 'w') as outfile:
    json.dump(fix, outfile, indent=1)

# for the data.dataformat fixture, remove unknown
file_fixtures = './data/fixtures/data.dataformat.json'
with open(file_fixtures) as ff:
    fix = json.load(ff)

for i, f in enumerate(fix):
    if f['fields']['name'] == 'unknown':
        fix.remove(f)

with open(file_fixtures, 'w') as outfile:
    json.dump(fix, outfile, indent=1)
