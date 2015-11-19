# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('subjects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='responsible_user',
            field=models.ForeignKey(default=0, related_name='subjects_responsible', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
