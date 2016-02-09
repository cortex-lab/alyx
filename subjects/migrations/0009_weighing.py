# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0008_auto_20160108_2108'),
    ]

    operations = [
        migrations.CreateModel(
            name='Weighing',
            fields=[
                ('action_ptr', models.OneToOneField(serialize=False, parent_link=True, to='subjects.Action', primary_key=True, auto_created=True)),
                ('weight', models.IntegerField()),
            ],
            bases=('subjects.action',),
        ),
    ]
