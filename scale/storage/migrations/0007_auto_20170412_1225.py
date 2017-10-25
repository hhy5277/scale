# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-04-12 12:25
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0006_auto_20170127_1423'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scalefile',
            name='meta_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name='workspace',
            name='json_config',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]