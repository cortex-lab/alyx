# Generated by Django 4.1.7 on 2023-06-16 11:38

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subjects', '0011_alter_subject_nickname'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subject',
            name='nickname',
            field=models.CharField(default='-', help_text="Easy-to-remember name (e.g. 'Hercules').", max_length=64, validators=[django.core.validators.RegexValidator('^[\\w.-]+$', 'Nicknames must only contain letters, numbers, hyphens and underscores. Dots are reserved for breeding subjects.')]),
        ),
    ]
