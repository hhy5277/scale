# -*- coding: utf-8 -*-


from django.db import models, migrations
import util.deprecation


class Migration(migrations.Migration):

    dependencies = [
        ('job', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobexecution',
            name='job_metrics',
            field=util.deprecation.JSONStringField(default={}, null=True, blank=True),
            preserve_default=True,
        ),
    ]
