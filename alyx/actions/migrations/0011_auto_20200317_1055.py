# Generated by Django 2.2.6 on 2020-03-17 10:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0010_session_extended_qc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='subjects.Project', verbose_name='Session Project'),
        ),
    ]
