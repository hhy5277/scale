# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-20 13:20
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0011_auto_20180821_1439'),
    ]

    operations = [
        migrations.RenameField(
            model_name='workspace',
            old_name='archived',
            new_name='deprecated',
        ),
        migrations.RemoveField(
            model_name='workspace',
            name='total_size',
        ),
        migrations.RemoveField(
            model_name='workspace',
            name='used_size',
        ),
    ]
