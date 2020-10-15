## do the synchronisation of IBL patcher files DMZ
import logging
from data.models import FileRecord, Dataset
import data.transfers as transfers

logger = logging.getLogger('data.transfers')
logger.setLevel(20)

# get the datasets that have one file record on the DMZ
dsets = FileRecord.objects.filter(data_repository__name='ibl_patcher'
                                  ).values_list('dataset', flat=True).distinct()
dsets = Dataset.objects.filter(pk__in=dsets)

# delete the filerecords that are on the server already
transfers.globus_delete_local_datasets(dsets, dry=False)


# redo the query
dsets = FileRecord.objects.filter(data_repository__name='ibl_patcher'
                                  ).values_list('dataset', flat=True).distinct()
dsets = Dataset.objects.filter(pk__in=dsets)

gc, tm = transfers.globus_transfer_datasets(dsets, dry=False)
# todo waitfor transfer to finish

# set the exist flag to true
frs = FileRecord.objects.filter(data_repository__globus_is_personal=False, dataset__in=dsets)
frs.update(exists=True)

# remove the data from the FTP DMZ using globus (this also removes file records from dB)
transfers.globus_delete_local_datasets(dsets, dry=False)
