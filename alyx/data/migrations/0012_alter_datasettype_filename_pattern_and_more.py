# Generated by Django 4.0.6 on 2022-07-07 17:39

import alyx.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0011_alter_datasettype_filename_pattern'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasettype',
            name='filename_pattern',
            field=alyx.base.CharNullField(blank=True, help_text="File name pattern (with wildcards) for this file in ALF naming convention. E.g. 'spikes.times.*' or '*.timestamps.*', or 'spikes.*.*' for a DataCollection, which would include all files starting with the word 'spikes'. NB: Case-insensitive matching.If null, the name field must match the object.attribute part of the filename.", max_length=255, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='datasettype',
            name='name',
            field=models.CharField(blank=True, help_text="Short identifying nickname, e.g. 'spikes.times'", max_length=255, unique=True),
        ),
    ]