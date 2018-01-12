# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-01-11 16:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('behavior', '0003_auto_20170821_0923'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventseries',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_eventseries_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='headtracking',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_headtracking_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='headtracking',
            name='movie',
            field=models.ForeignKey(blank=True, help_text='Link to raw data', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='head_tracking_movie', to='data.Dataset'),
        ),
        migrations.AlterField(
            model_name='headtracking',
            name='x_y_theta',
            field=models.ForeignKey(blank=True, help_text='3*n timeseries giving x and y coordinates of head plus angle', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='head_tracking_x_y_d', to='data.Dataset'),
        ),
        migrations.AlterField(
            model_name='intervalseries',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_intervalseries_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='optogeneticstimulus',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_optogeneticstimulus_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='pharmacology',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_pharmacology_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='pupiltracking',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_pupiltracking_created_by_related', to='misc.OrderedUser'),
        ),
        migrations.AlterField(
            model_name='pupiltracking',
            name='movie',
            field=models.ForeignKey(blank=True, help_text='Link to raw data', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pupil_tracking_movie', to='data.Dataset'),
        ),
        migrations.AlterField(
            model_name='pupiltracking',
            name='x_y_d',
            field=models.ForeignKey(blank=True, help_text='n*3 timeseries giving x and y coordinates of center plus diameter', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pupil_tracking_x_y_d', to='data.Dataset'),
        ),
    ]
