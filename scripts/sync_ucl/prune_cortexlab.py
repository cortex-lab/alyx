#!/usr/bin/env python3
from django.core.management import call_command

from subjects.models import Subject, Project
from actions.models import Session
from misc.models import Lab
from data.models import Dataset, DatasetType
json_file_out = '../scripts/sync_ucl/cortexlab_pruned.json'

# remove all the database that is not related to IBL
Subject.objects.using('cortexlab').exclude(projects__name__icontains='ibl').delete()

# then remove base Sessions
Session.objects.using('cortexlab').filter(type='Base').delete()

# the sessions should have a proper project name labeled
ses = Session.objects.using('cortexlab').all()
pk_proj = Project.objects.get(name='ibl_cortexlab').pk
proj = Project.objects.using('cortexlab').get(pk=pk_proj)
ses.update(project=proj)

# the sessions should also have the cortexlab lab field properly labeled before import
if Lab.objects.using('cortexlab').filter(name='cortexlab').count() == 0:
    lab_dict = {'pk': '4027da48-7be3-43ec-a222-f75dffe36872',
                'name': 'cortexlab'}
    lab = Lab.objects.using('cortexlab').create(**lab_dict)
    lab.save()
else:
    lab = Lab.objects.using('cortexlab').get(name='cortexlab')
ses.update(lab=lab)

# we want to make sure that no other dataset type than those defined in IBL are imported
dtypes = [dt[0] for dt in DatasetType.objects.all().values_list('name')]
Dataset.objects.using('cortexlab').exclude(dataset_type__name__in=dtypes).delete()
Dataset.objects.using('cortexlab').filter(dataset_type__name='Unknown').delete()

##
# those are the init fixtures that could have different names depending on the location
# (ibl_cortexlab versus cortexlab for example)
# they share primary keys accross databases but not necessarily the other fields
init_fixtures = [# 'actions.proceduretype',
                 # 'actions.watertype',
                 'data.dataformat',
                 'data.datarepositorytype',
                 # 'data.datasettype',
                 'misc.lab',
                 'subjects.project']

# those are system fixtures and should not be migrated
system_excludes = ['admin.logentry',
                   'auth.group',
                   'authtoken.token',
                   'contenttypes',
                   'auth.permission',
                   'reversion.version',
                   'reversion.revision',
                   'sessions.session']

excludes = []
excludes.extend(init_fixtures)
excludes.extend(system_excludes)

with open(json_file_out, 'w') as out:  # Point stdout at a file for dumping data to.
    call_command('dumpdata', format='json', indent=1, stdout=out, database='cortexlab',
                 exclude=excludes)
# ./manage.py dumpdata -e contenttypes -e auth.permission -e reversion.version
# -e reversion.revision -e admin.logentry -e authtoken.token -e auth.group --indent 1
# --database cortexlab -o ../scripts/sync_ucl/cortexlab.json
