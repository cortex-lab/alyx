# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-01-11 16:34
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0003_auto_20170821_0923'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataFormat',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('name', models.CharField(blank=True, help_text="short identifying nickname, e..g 'npy'.", max_length=255, unique=True)),
                ('description', models.CharField(blank=True, help_text="Human-readable description of the file format e.g. 'npy-formatted square numerical array'.", max_length=255, unique=True)),
                ('alf_filename', models.CharField(blank=True, help_text="string (with wildcards) identifying these files, e.g. '*.*.npy'.", max_length=255, unique=True)),
                ('matlab_loader_function', models.CharField(blank=True, help_text="Name of MATLAB loader function'.", max_length=255, unique=True)),
                ('python_loader_function', models.CharField(blank=True, help_text="Name of Python loader function'.", max_length=255, unique=True)),
            ],
            options={
                'verbose_name_plural': 'data formats',
            },
        ),
        migrations.RemoveField(
            model_name='datacollection',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='datacollection',
            name='data',
        ),
        migrations.RemoveField(
            model_name='datacollection',
            name='provenance_directory',
        ),
        migrations.RemoveField(
            model_name='datacollection',
            name='session',
        ),
        migrations.RemoveField(
            model_name='eventseries',
            name='datacollection_ptr',
        ),
        migrations.RemoveField(
            model_name='eventseries',
            name='times',
        ),
        migrations.RemoveField(
            model_name='eventseries',
            name='timescale',
        ),
        migrations.RemoveField(
            model_name='intervalseries',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='intervalseries',
            name='intervals',
        ),
        migrations.RemoveField(
            model_name='intervalseries',
            name='provenance_directory',
        ),
        migrations.RemoveField(
            model_name='intervalseries',
            name='session',
        ),
        migrations.RemoveField(
            model_name='intervalseries',
            name='timescale',
        ),
        migrations.RemoveField(
            model_name='timeseries',
            name='datacollection_ptr',
        ),
        migrations.RemoveField(
            model_name='timeseries',
            name='timescale',
        ),
        migrations.RemoveField(
            model_name='timeseries',
            name='timestamps',
        ),
        migrations.AddField(
            model_name='datarepository',
            name='globus_endpoint_id',
            field=models.UUIDField(blank=True, help_text=' UUID of the globus endpoint', null=True),
        ),
        migrations.AddField(
            model_name='dataset',
            name='parent_dataset',
            field=models.ForeignKey(blank=True, help_text='hierachical parent of this Dataset.', null=True, on_delete=django.db.models.deletion.CASCADE, to='data.Dataset'),
        ),
        migrations.AddField(
            model_name='dataset',
            name='timescale',
            field=models.ForeignKey(blank=True, help_text='Associated time scale (for time series datasets only).', null=True, on_delete=django.db.models.deletion.CASCADE, to='data.Timescale'),
        ),
        migrations.AddField(
            model_name='datasettype',
            name='alf_filename',
            field=models.CharField(blank=True, help_text="File name pattern (with wildcards) for this file in ALF naming convention. E.g. 'spikes.times.*' or '*.timestamps.*', or 'spikes.*.*' for a DataCollection, which would include all files starting with the word 'spikes'.", max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='datasettype',
            name='description',
            field=models.CharField(blank=True, help_text="Human-readable description of data type. Should say what is in the file, and how to read it. For DataCollections, it should list what Datasets are expected in the the collection. E.g. 'Files related to spike events, including spikes.times.npy, spikes.clusters.npy, spikes.amps.npy, spikes.depths.npy", max_length=1023),
        ),
        migrations.AddField(
            model_name='filerecord',
            name='exists',
            field=models.BooleanField(default=False, help_text='Whether the file exists in the data repository'),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='data_dataset_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='datasettype',
            name='name',
            field=models.CharField(blank=True, help_text="Short identifying nickname, e.g. 'spikes'", max_length=255, unique=True),
        ),
        migrations.DeleteModel(
            name='DataCollection',
        ),
    ]
