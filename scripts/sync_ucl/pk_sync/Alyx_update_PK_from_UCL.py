from django.core.management import call_command
from data.models import DataRepositoryType, DataRepository, DataFormat, DatasetType, Dataset
from subjects.models import Sequence, Project
from actions.models import Session
import json


FILE_UCL_JSON_DUMP_INP = '../scripts/sync_ucl/cortexlab.json'
FILE_IBL_JSON_DUMP_INP = '../scripts/sync_ucl/ibl-alyx-pkupdate-before.json'
FILE_IBL_JSON_DUMP_OUT = '../scripts/sync_ucl/ibl-alyx-pkupdate-after.json'
CHECK_UCL_PK = True

# remove all dataset types that are not IBL
Dataset.objects.exclude(dataset_type__name__contains='_ibl_').exclude(
    dataset_type__name__contains='_rigbox_').delete()
DatasetType.objects.exclude(name__contains='_ibl_').exclude(name__contains='_rigbox_').delete()

# remove sessions from UCL as we'll reimport everything depending on them clean
pk_proj_ibl = Project.objects.get(name='ibl_cortexlab').pk
ses_ibl = Session.objects.using('default').filter(project=pk_proj_ibl).delete()

# For the next PK, it's impossible to do it in sql, dump a json and regexp the uuids, then reload
print('dump full IBL')
with open(FILE_IBL_JSON_DUMP_INP, 'w') as out:  # Point stdout at a file for dumping data to.
    call_command('dumpdata', format='json', indent=1, stdout=out, database='default')

excludes = ['admin.logentry',
            'authtoken.token',
            'contenttypes',
            'auth.permission',
            'reversion.version',
            'reversion.revision',
            'sessions.session',
            'auth.group']

print('dump full Cortexlab')
with open(FILE_UCL_JSON_DUMP_INP, 'w') as out:  # Point stdout at a file for dumping data to.
    call_command('dumpdata', format='json', indent=1, stdout=out, database='cortexlab',
                 exclude=excludes)

# Load the database dump.
with open(FILE_UCL_JSON_DUMP_INP, 'r') as f:
    DB_UCL = json.load(f)

# modelClass = Sequence
# fixture_name = modelClass._meta.label_lower
# loop over all items and look at PK mismatches betweeen the two databases

pk_ibl2ucl = {}
for item in DB_UCL:
    if item['model'] == 'subjects.sequence':
        dbitem = Sequence.objects.filter(name=item['fields']['name'])
        if dbitem.count() == 0:
            continue
        if item['pk'] != str(dbitem[0].pk):
            pk_ibl2ucl[str(dbitem[0].pk)] = item['pk']
            print('subjects.sequence: ' + str(item['pk']) + '  ' + str(dbitem[0].pk) +
                  '  ' + item['fields']['name'])
    if item['model'] == 'data.datarepositorytype':
        dbitem = DataRepositoryType.objects.filter(name=item['fields']['name'])
        if dbitem.count() == 0:
            continue
        if item['pk'] != str(dbitem[0].pk):
            print('data.datarepositorytype: ' + str(item['pk']) + '  ' + str(dbitem[0].pk) +
                  '  ' + item['fields']['name'])
            pk_ibl2ucl[str(dbitem[0].pk)] = item['pk']
    if item['model'] == 'data.datarepository':
        dbitem = DataRepository.objects.filter(name=item['fields']['name'])
        if dbitem.count() == 0:
            continue
        if item['pk'] != str(dbitem[0].pk):
            print('data.datarepository: ' + str(item['pk']) + '  ' + str(dbitem[0].pk) +
                  '  ' + item['fields']['name'])
            pk_ibl2ucl[str(dbitem[0].pk)] = item['pk']
    if item['model'] == 'data.dataformat':
        dbitem = DataFormat.objects.filter(name=item['fields']['name'])
        if dbitem.count() == 0:
            continue
        if item['pk'] != str(dbitem[0].pk):
            print('data.dataformat: ' + str(item['pk']) + '  ' + str(dbitem[0].pk) +
                  '  ' + item['fields']['name'])
            pk_ibl2ucl[str(dbitem[0].pk)] = item['pk']
    if item['model'] == 'data.datasettype':
        dbitem = DatasetType.objects.filter(name=item['fields']['name'])
        if dbitem.count() == 0:
            continue
        if item['pk'] != str(dbitem[0].pk):
            print('data.datasettype ' + str(item['pk']) + '  ' + str(dbitem[0].pk) +
                  '  ' + item['fields']['name'])
            pk_ibl2ucl[str(dbitem[0].pk)] = item['pk']


# Now regexp into the json files the PK
with open(FILE_IBL_JSON_DUMP_INP) as f:
    text = f.read()

for k in pk_ibl2ucl:
    text = text.replace(k, pk_ibl2ucl[k])

with open(FILE_IBL_JSON_DUMP_OUT, "w") as f:
    f.write(text)
