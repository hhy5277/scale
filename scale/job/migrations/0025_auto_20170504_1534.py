# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-04 19:34


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('job', '0024_auto_20170412_1225'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobexecution',
            name='ended',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
