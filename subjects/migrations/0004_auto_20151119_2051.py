# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0003_auto_20151119_2032'),
    ]

    operations = [
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, serialize=False, primary_key=True)),
            ],
        ),
        migrations.AddField(
            model_name='subject',
            name='notes',
            field=models.TextField(default=0),
            preserve_default=False,
        ),
    ]
