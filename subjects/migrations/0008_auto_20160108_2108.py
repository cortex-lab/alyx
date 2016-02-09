# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0007_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='end_date_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='action',
            name='start_date_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
