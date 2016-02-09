# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0005_auto_20151125_1531'),
    ]

    operations = [
        migrations.CreateModel(
            name='Species',
            fields=[
                ('binomial', models.CharField(serialize=False, primary_key=True, max_length=255)),
                ('display_name', models.CharField(max_length=255)),
            ],
        ),
        migrations.AlterField(
            model_name='subject',
            name='species',
            field=models.ForeignKey(to='subjects.Species'),
        ),
    ]
