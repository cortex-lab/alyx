# Generated by Django 2.1.3 on 2019-01-17 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0005_auto_20190116_1422'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surgery',
            name='outcome_type',
            field=models.CharField(blank=True, choices=[('a', 'Acute'), ('r', 'Recovery'), ('n', 'Non-recovery')], max_length=1),
        ),
    ]
