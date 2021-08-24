#!/usr/bin/env python3
from django.core.management import call_command

from subjects.models import Subject, Project, SubjectRequest
from actions.models import Session, Surgery, NotificationRule, Notification
from misc.models import Lab, LabMember, LabLocation
from data.models import Dataset, DatasetType, DataRepository, FileRecord
from experiments.models import ProbeInsertion, TrajectoryEstimate
from jobs.models import Task

json_file_out = '../scripts/sync_ucl/cortexlab_pruned.json'

# remove all subjects that never had anything to do with IBL
ses = Session.objects.using('cortexlab').filter(project__name__icontains='ibl')
sub_ibl = list(ses.values_list('subject', flat=True))
sub_ibl += list(Subject.objects.values_list('pk', flat=True))
sub_ibl += list(Subject.objects.using('cortexlab').filter(
    projects__name__icontains='ibl').values_list('pk', flat=True))
Subject.objects.using('cortexlab').exclude(pk__in=sub_ibl).delete()

# then remove base Sessions
Session.objects.using('cortexlab').filter(type='Base').delete()

# remove the subject requests
SubjectRequest.objects.using('cortexlab').all().delete()

# remove all sessions that are not part of IBL project
Session.objects.using('cortexlab').exclude(project__name__icontains='ibl').delete()

# also if cortexlab sessions have been removed on the server, remove them
ses_ucl = Session.objects.using('cortexlab').all().values_list('pk', flat=True)
ses_loc2remove = Session.objects.filter(lab__pk='4027da48-7be3-43ec-a222-f75dffe36872')\
    .exclude(pk__in=list(ses_ucl))
ses_loc2remove.delete()

# the sessions should also have the cortexlab lab field properly labeled before import
if Lab.objects.using('cortexlab').filter(name='cortexlab').count() == 0:
    lab_dict = {'pk': '4027da48-7be3-43ec-a222-f75dffe36872',
                'name': 'cortexlab'}
    lab = Lab.objects.using('cortexlab').create(**lab_dict)
    lab.save()
else:
    lab = Lab.objects.using('cortexlab').get(name='cortexlab')
ses = Session.objects.using('cortexlab').all()
ses.update(lab=lab)

# the lablocations should have the lab field set to cortexlab
LabLocation.objects.using('cortexlab').update(lab=lab)

# we want to make sure that no other dataset type than those defined in IBL are imported
dtypes = [dt[0] for dt in DatasetType.objects.all().values_list('name')]
Dataset.objects.using('cortexlab').exclude(dataset_type__name__in=dtypes).delete()
Dataset.objects.using('cortexlab').filter(dataset_type__name='Unknown').delete()
Dataset.objects.using('cortexlab').filter(dataset_type__name='unknown').delete()

# we want to make sure that no other file record than the ones in already existing repositories
# are imported
repos = list(DataRepository.objects.all().values_list('pk', flat=True))
FileRecord.objects.using('cortexlab').exclude(data_repository__in=repos).delete()
DataRepository.objects.using('cortexlab').exclude(pk__in=repos).delete()

# sync the datasets


# import projects from cortexlab. remove those that don't correspond to any session
pk_projs = list(ses_ucl.values_list('project', flat=True).distinct())
pk_projs += list(Project.objects.values_list('pk', flat=True))

Project.objects.using('cortexlab').exclude(pk__in=pk_projs).delete()

# only imports users that are relevant to IBL
users_to_import = ['cyrille', 'Gaelle', 'kenneth', 'lauren', 'matteo', 'miles', 'nick', 'olivier',
                   'Karolina_Socha', 'Hamish', 'laura', 'niccolo']
users_to_leave = LabMember.objects.using('cortexlab').exclude(username__in=users_to_import)
users_to_keep = Dataset.objects.using('cortexlab').values_list('created_by', flat=True).distinct()
users_to_leave = users_to_leave.exclude(pk__in=users_to_keep)
users_to_keep = Session.objects.using('cortexlab').values_list('users', flat=True)
users_to_leave = users_to_leave.exclude(pk__in=users_to_keep)
users_to_keep = Subject.objects.using('cortexlab').values_list('responsible_user', flat=True)
users_to_leave = users_to_leave.exclude(pk__in=users_to_keep)
users_to_keep = Surgery.objects.using('cortexlab').values_list('users', flat=True)
users_to_leave = users_to_leave.exclude(pk__in=users_to_keep)
users_to_leave.delete()

# remove notification rules from cortexlab and notifications that haven't been sent yet
NotificationRule.objects.using('cortexlab').all().delete()
Notification.objects.using('cortexlab').filter(sent_at__isnull=True).delete()

"""
probe insertion objects may have been updated upstreams. In this case the insertion update MO
was to delete the probe insertion before repopulating downstream tables. This creates
an integrity error on import. To avoid this the duplicate insertions have to be removed
from cortex lab before import. IBL always priority.
Sometimes there are some trajectories estimates in the cortexlab that is not in IBL, in this case
create them
"""
session_pname = set(ProbeInsertion.objects.using('cortexlab').values_list('session', 'name')
                    ).intersection(set(ProbeInsertion.objects.values_list('session', 'name')))
for sp in session_pname:
    pi_cortexlab = ProbeInsertion.objects.using('cortexlab').get(session=sp[0], name=sp[1])
    pi_ibl = ProbeInsertion.objects.get(session=sp[0], name=sp[1])
    for traj_c in pi_cortexlab.trajectory_estimate.all():
        traj_i = pi_ibl.trajectory_estimate.filter(provenance=traj_c.provenance)
        if traj_i.count() == 0:
            t = traj_c.__dict__.copy()
            t.pop('_state')
            t['probe_insertion_id'] = pi_ibl.id
            TrajectoryEstimate.objects.create(**t)
    pi_cortexlab.delete()


"""
Sync the datasets 1/2. Look for duplicates. If for one reason or another a file has been created
on the IBL database and cortexlab (new dataset patch), there will be a consistency error.
In this case we remove the offending datasets from IBL: the UCL version always has priority
(at some point using pandas might be much easier and legible)
"""
dfields = ('session', 'collection', 'name')
cds_pk = list(Dataset.objects.using('cortexlab').values_list('pk', flat=True))
ids_pk = list(Dataset.objects.filter(session__lab__name='cortexlab').values_list('pk', flat=True))
pk2check = set(ids_pk).difference(cds_pk)
ibl_datasets = Dataset.objects.filter(pk__in=pk2check)
ids = ibl_datasets.values_list(*dfields)
cds = Dataset.objects.using('cortexlab').values_list(*dfields)

# there should not be a whole lot of them so loop
duplicates = set(cds).intersection(ids)

for dup in duplicates:
    dset = ibl_datasets.get(session=dup[0], collection=dup[1], name=dup[2])
    dset.delete()

"""
Sync the datasets 2/2. If a dataset already exist on both database but has a different hash
then it means its' been patched. In this case we set the filerecord from the server
to exist=False and reset the json field
(at some point using pandas might be much easier and legible)
"""

dfields = ('pk', 'hash')
cds = Dataset.objects.using('cortexlab').values_list(*dfields)
cds_pk = [ds[0] for ds in cds]

ids = Dataset.objects.filter(pk__in=cds_pk).values_list(*dfields)
ids_pk = [ds[0] for ds in ids]
ids_md5 = [ds[1] for ds in ids]
cds = Dataset.objects.using('cortexlab').filter(pk__in=ids_pk).values_list(*dfields)

dpk = [s[0] for s in set(cds).difference(set(ids))]
FileRecord.objects.filter(data_repository__globus_is_personal=False, dataset__in=dpk).update(
    exists=False, json=None)

"""
Sync the tasks: they're all imported except the DLC ones: this is kind of a hack for now
Spike sorting will have to be the same. Need to think of a way to centralize the task management
System in only one database. Will be easier when ONE2 is realeased
"""
task_names_to_exclude = ['TrainingDLC', 'EphysDLC']
dlc_tasks = Task.objects.using('cortexlab').filter(name__in=task_names_to_exclude)
ctasks = dlc_tasks.values_list('pk', flat=True)
ibltasks = Task.objects.filter(name__in=task_names_to_exclude).values_list('pk', flat=True)
t2add = list(set(list(ctasks)).difference(list(ibltasks)))
dlc_tasks.exclude(id__in=t2add).delete()

"""
Export all the pruned cortexlab database as Json so it can be loaded back into the IBL one
those are the init fixtures that could have different names depending on the location
(ibl_cortexlab versus cortexlab for example)
they share primary keys accross databases but not necessarily the other fields
"""

init_fixtures = ['data.dataformat',
                 'data.datarepositorytype',
                 'data.datasettype',
                 'misc.lab',
                 #  'subjects.project',
                 #  'actions.proceduretype',
                 #  'actions.watertype',
                 ]

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
