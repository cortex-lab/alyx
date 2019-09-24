from operator import itemgetter
from data.models import DatasetType, Dataset

# All existing dataset types.
dataset_types = set(map(itemgetter(0), DatasetType.objects.values_list('name')))

# Dataset types that exist with AND without _ibl_ prefix need to be merged.
duplicates = set('_ibl_' + name for name in dataset_types).intersection(dataset_types)

# Reassign the object.attribute datasets to _ibl_object.attribute
for name in duplicates:
    name_noibl = name[5:]
    assert name_noibl in dataset_types
    datasets = Dataset.objects.filter(dataset_type__name=name_noibl)
    assert name.startswith('_ibl_')
    print("Updating %d datasets with dataset type %s." % (len(datasets), name))
    datasets.update(dataset_type=DatasetType.objects.get(name=name))

    # There should no longer be any dataset with the reassigned dataset types.
    assert len(Dataset.objects.filter(dataset_type__name=name_noibl)) == 0

    # So we remove it.
    DatasetType.objects.get(name=name_noibl).delete()
    print("Dataset type %s removed." % name_noibl)
