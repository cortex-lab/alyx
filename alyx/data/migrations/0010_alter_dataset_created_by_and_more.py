# Generated by Django 4.0.3 on 2022-03-30 15:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0017_alter_chronicrecording_subject_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('data', '0009_auto_20210624_1253'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_created_by_related', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='provenance_directory',
            field=models.ForeignKey(blank=True, help_text='link to directory containing intermediate results', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_provenance_related', to='data.dataset'),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='session',
            field=models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_session_related', to='actions.session'),
        ),
        migrations.AlterField(
            model_name='datasettype',
            name='created_by',
            field=models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_created_by_related', to=settings.AUTH_USER_MODEL),
        ),
    ]
