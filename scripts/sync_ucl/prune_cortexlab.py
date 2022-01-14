#!/usr/bin/env python3
import numpy as np

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
# but keep histology sessions
ses_loc2remove = ses_loc2remove.exclude(task_protocol__startswith='SWC_Histology_Serial2P')
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
Sync the datasets 1/3. Compute primary keys
"""

dfields = ('session', 'collection', 'name')
# Primary keys of all datasets in cortexlab database
cds_pk = set(Dataset.objects.using('cortexlab').values_list('pk', flat=True))
# Primary keys of all datasets with lab name cortexlab in ibl database
ids_pk = set(Dataset.objects.filter(session__lab__name='cortexlab').values_list('pk', flat=True))

"""
Sync the datasets 2/3. Set(IBL) - Set(Cortexlab)
Look for duplicates. If for one reason or another a file has been created
on the IBL database and cortexlab (new dataset patch), there will be a consistency error.
In this case we remove the offending datasets from IBL: the UCL version always has priority
(at some point using pandas might be much easier and legible)
"""
# Here we are looking for duplicated that DO NOT have the same primary key, but the same session, collection and name
# Find the datasets that only exist in the IBL database, load session, collection and name
pk2check = ids_pk.difference(cds_pk)
ibl_datasets = Dataset.objects.filter(pk__in=pk2check)
ids = ibl_datasets.values_list(*dfields)
# Again load all datasets from cortexlab database, this time with session, collection and name
cds = Dataset.objects.using('cortexlab').values_list(*dfields)

# Check for duplicates with the same session, collection and name
duplicates = set(cds).intersection(ids)
# there should not be a whole lot of them so loop
for dup in duplicates:
    # Get the full dataset entry from the ibl database and delete
    dset = ibl_datasets.get(session=dup[0], collection=dup[1], name=dup[2])
    dset.delete()

"""
Sync the datasets 3/3. Set(IBL) intersection Set(Cortexlab)
If a dataset already exist on both database but has a different hash
then it means its' been patched. In this case we get the latest dataset as per the auto-update
and set IBL filerecord to exist=False and reset the json field
(at some point using pandas might be much easier and legible)
"""
dfields = ('pk', 'hash')

set_cortex_lab_only = cds_pk.difference(ids_pk)
set_ibl_only = ids_pk.difference(cds_pk)
# get the interection querysets
cqs = Dataset.objects.using('cortexlab').exclude(pk__in=set_cortex_lab_only).order_by('pk').values_list(*dfields)
iqs = Dataset.objects.filter(session__lab__name='cortexlab').exclude(pk__in=set_ibl_only).order_by('pk').values_list(*dfields)

# manual check but this is expensive
# assert len(set(iqs).difference(set(cqs))) == len(set(cqs).difference(set(iqs)))

# this is the set of pks for which there is a md5 mismatch - for all the others, do not import anything by deleting
# many datasets from the cortexlab database
dpk = [s[0] for s in set(cds).difference(set(ids))]
Dataset.objects.using('cortexlab').exclude(pk__in=set_cortex_lab_only.union(dpk)).delete()


dfields = ('pk', 'hash', 'auto_datetime')
cqs_md5 = Dataset.objects.using('cortexlab').filter(pk__in=dpk).order_by('pk')
iqs_md5 = Dataset.objects.filter(session__lab__name='cortexlab', pk__in=dpk).order_by('pk')

ti = np.array(iqs_md5.values_list('auto_datetime', flat=True)).astype(np.datetime64)
tc = np.array(cqs_md5.values_list('auto_datetime', flat=True)).astype(np.datetime64)
# those are the indices where the autodatetiem from IBL is posterior to cortexlab - do not import by deleting the datasets
# from the cortexlab database
ind_ibl = np.where(ti >= tc)[0]
pk2remove = list(np.array(iqs_md5.values_list('pk', flat=True))[ind_ibl])
Dataset.objects.using('cortexlab').filter(pk__in=pk2remove).delete()
# for those that will imported from UCL, set the filerecord status to exist=False fr the local server fierecords
ind_ucl = np.where(tc > ti)[0]
pk2import = list(np.array(iqs_md5.values_list('pk', flat=True))[ind_ucl])
FileRecord.objects.filter(dataset__in=pk2import).update(exists=False, json=None)

"""
Sync the tasks 1/2: For DLC tasks there might be duplicates, as we sometimes run them as batch on remote servers.
Import the cortexlab tasks unless there is a NEWER version in the ibl database
"""
task_names_to_check = ['TrainingDLC', 'EphysDLC']
# Get the pks of the DLC tasks from both the cortexlab db and ibl db with cortexlab as lab name
cortex_dlc_pk = set(Task.objects.using('cortexlab').filter(name__in=task_names_to_check).values_list('pk', flat=True))
ibl_dlc_pk = set(Task.objects.filter(session__lab__name='cortexlab').filter(name__in=task_names_to_check
                                                                            ).values_list('pk', flat=True))
# Get the intersection primary keys and the respective tasks from each DB
duplicate_pk = cortex_dlc_pk.intersection(ibl_dlc_pk)
dlc_cortex = Task.objects.using('cortexlab').filter(pk__in=duplicate_pk).order_by('pk')
dlc_ibl = Task.objects.filter(session__lab__name='cortexlab').filter(pk__in=duplicate_pk).order_by('pk')
# Get time stamps from those tasks
times_cortex = np.array(dlc_cortex.values_list('datetime', flat=True)).astype(np.datetime64)
times_ibl = np.array(dlc_ibl.values_list('datetime', flat=True)).astype(np.datetime64)
# Indices where datetime from IBL is newer than cortexlab -- do not import by deleting the datasets from cortexlab db
keep_ibl = np.where(times_ibl >= times_cortex)[0]
pk_del_cortex = list(np.array(dlc_cortex.values_list('pk', flat=True))[keep_ibl])
Task.objects.using('cortexlab').filter(pk__in=pk_del_cortex).delete()


"""
Sync the tasks 2/2: for the other tasks we want to make sure there are no duplicate tasks with
different ids that have been made on IBL and cortex lab database. In the case of duplicates cortex
lab database are kept and IBL deleted
"""
task_names_to_exclude = ['TrainingDLC', 'EphysDLC']
cortex_eids = Task.objects.using('cortexlab').exclude(name__in=task_names_to_exclude).values_list('session', flat=True)
ibl_eids = Task.objects.all().filter(session__lab__name='cortexlab').exclude(
    name__in=task_names_to_exclude).values_list('session', flat=True)
# finds eids that have tasks on both ibl and cortex lab database
overlap_eids = set(cortex_eids).intersection(ibl_eids)

dfields = ('id', 'name', 'session')
task_cortex = Task.objects.using('cortexlab').filter(session__in=overlap_eids).exclude(name__in=task_names_to_exclude)
cids = task_cortex.values_list(*dfields)

task_ibl = Task.objects.all().filter(session__in=overlap_eids).exclude(name__in=task_names_to_exclude)
ids = task_ibl.values_list(*dfields)

# find the tasks that are not common to both
different = set(cids).symmetric_difference(ids)

# find only those that are on the IBL database
duplicates = different.intersection(ids)

# delete the duplicates
for dup in duplicates:
    ts = task_ibl.get(id=dup[0], name=dup[1], session=dup[2])
    ts.delete()


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
