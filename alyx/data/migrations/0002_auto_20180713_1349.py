# Generated by Django 2.0.6 on 2018-07-13 13:49

import data.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('data', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('actions', '0002_auto_20180713_1349'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasettype',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_datasettype_created_by_related', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dataset',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_dataset_created_by_related', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dataset',
            name='data_format',
            field=models.ForeignKey(default=data.models.default_data_format, on_delete=django.db.models.deletion.SET_DEFAULT, to='data.DataFormat'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='dataset_type',
            field=models.ForeignKey(default=data.models.default_dataset_type, on_delete=django.db.models.deletion.SET_DEFAULT, to='data.DatasetType'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='provenance_directory',
            field=models.ForeignKey(blank=True, help_text='link to directory containing intermediate results', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_dataset_provenance_related', to='data.Dataset'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='session',
            field=models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_dataset_session_related', to='actions.Session'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='timescale',
            field=models.ForeignKey(blank=True, help_text='Associated time scale (for time series datasets only).', null=True, on_delete=django.db.models.deletion.CASCADE, to='data.Timescale'),
        ),
        migrations.AddField(
            model_name='datarepository',
            name='repository_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='data.DataRepositoryType'),
        ),
    ]
