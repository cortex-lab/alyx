import time

from actions.models import Session
from data.models import FileRecord, DataRepository
import data.transfers

PATCHING_GLOBUS_ID = "4ef795c6-05e0-11e9-9f96-0a06afd4a22e"

sessions = Session.objects.filter(id="fb053e3d-4ca5-447f-a2ca-fedb93138864")

fr_local = FileRecord.objects.filter(dataset__session__in=sessions,
                                     data_repository__globus_is_personal=True)
fr_server = FileRecord.objects.filter(dataset__session__in=sessions,
                                      data_repository__globus_is_personal=False)

assert(fr_local.count() == fr_server.count())

fr_server.update(exists=False)
files_repos_save = fr_local.values_list('id', 'data_repository')
fr_local.update()

repo = fr_local.values_list('data_repository', flat=True).distinct()
assert(repo.count() == 1)
repo = DataRepository.objects.get(id=repo[0])

globus_id_save = repo.globus_endpoint_id
repo.globus_endpoint_id = PATCHING_GLOBUS_ID
repo.save()

print('Transfering files over')
data.transfers.bulk_transfer(lab=repo.lab_set.get().name)
repo.globus_endpoint_id = globus_id_save
repo.save()

print('Waiting 10 mins to perform a read after write')
time.sleep(600)
data.transfers.bulk_sync(lab=repo.lab_set.get().name)
