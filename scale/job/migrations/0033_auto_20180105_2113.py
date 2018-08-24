# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-01-05 21:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('job', '0032_job_node'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='source_ended',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='job',
            name='source_started',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]