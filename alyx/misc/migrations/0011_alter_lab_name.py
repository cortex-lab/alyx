# Generated by Django 5.1.2 on 2024-11-14 11:01

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('misc', '0010_alter_lab_timezone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='name',
            field=models.CharField(max_length=255, unique=True, validators=[django.core.validators.RegexValidator('^\\w+$', 'Lab name must only contain letters, numbers, and underscores.')]),
        ),
    ]