# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-09-11 17:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0006_scheduler_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduler',
            name='num_message_handlers',
            field=models.IntegerField(default=2),
        ),
    ]