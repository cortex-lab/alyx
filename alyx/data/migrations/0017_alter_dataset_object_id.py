# Generated by Django 4.1.7 on 2023-06-16 09:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0016_alter_dataset_collection_alter_revision_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='object_id',
            field=models.UUIDField(blank=True, help_text='UUID of an object whose type matches content_type.', null=True),
        ),
    ]
