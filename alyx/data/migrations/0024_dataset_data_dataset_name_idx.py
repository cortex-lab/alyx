from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """Index data_dataset.name, which the `?datasets=` REST filters look up.

    Built concurrently: data_dataset is ~1.4 GB and continuously written by the ingest pipeline,
    and a regular CREATE INDEX would hold an ACCESS EXCLUSIVE lock on it for the duration of the
    build. Concurrent builds cannot run inside a transaction, hence atomic = False.
    """

    atomic = False

    dependencies = [
        ('data', '0023_datanotice'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='dataset',
            index=models.Index(fields=['name'], name='data_dataset_name_idx'),
        ),
    ]
