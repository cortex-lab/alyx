# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, serialize=False)),
                ('nickname', models.CharField(max_length=255)),
                ('species', models.CharField(max_length=2, default='MO', choices=[('MO', 'Laboratory mouse'), ('RA', 'Laboratory rat'), ('RM', 'Rhesus macaque'), ('HU', 'Human')])),
                ('sex', models.CharField(max_length=1, default='U', choices=[('M', 'Male'), ('F', 'Female'), ('U', 'Unknown')])),
                ('strain', models.CharField(max_length=255)),
                ('genotype', models.CharField(max_length=255)),
                ('source', models.CharField(max_length=255)),
                ('birth_date_time', models.DateTimeField(null=True, blank=True)),
                ('death_date_time', models.DateTimeField(null=True, blank=True)),
                ('created_date_time', models.DateTimeField(auto_now_add=True)),
                ('modified_date_time', models.DateTimeField(auto_now=True)),
                ('created_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='subjects_created')),
                ('modified_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='subjects_last_modified')),
            ],
        ),
    ]
