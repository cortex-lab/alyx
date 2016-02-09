# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('subjects', '0006_auto_20160101_1124'),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.UUIDField(editable=False, serialize=False, default=uuid.uuid4, primary_key=True)),
                ('narrative', models.TextField(blank=True, null=True)),
                ('location', models.CharField(max_length=255)),
                ('subject', models.ForeignKey(to='subjects.Subject')),
                ('users', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
