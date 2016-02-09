# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0004_auto_20151119_2051'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Experiment',
        ),
        migrations.AddField(
            model_name='subject',
            name='description',
            field=models.CharField(default=0, max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='subject',
            name='notes',
            field=models.TextField(blank=True, null=True),
        ),
    ]
