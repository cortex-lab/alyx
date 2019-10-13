# Generated by Django 2.2.6 on 2019-10-07 19:51

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0006_cull_cullmethod_cullreason'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='qc',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Quality control JSON field', null=True),
        ),
    ]