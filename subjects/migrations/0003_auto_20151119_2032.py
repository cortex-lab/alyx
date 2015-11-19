# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0002_subject_responsible_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subject',
            name='created_date_time',
        ),
        migrations.RemoveField(
            model_name='subject',
            name='created_user',
        ),
        migrations.RemoveField(
            model_name='subject',
            name='modified_date_time',
        ),
        migrations.RemoveField(
            model_name='subject',
            name='modified_user',
        ),
    ]
