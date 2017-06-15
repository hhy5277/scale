# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-15 20:52
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('job', '0026_auto_20170510_1151'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobexecution',
            name='resources',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='jobtype',
            name='custom_resources',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]
