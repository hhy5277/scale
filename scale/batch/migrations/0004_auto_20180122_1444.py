# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-01-22 14:44


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('batch', '0003_auto_20170706_1948'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batch',
            name='creator_job',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='batch_creator_job', to='job.Job'),
        ),
    ]
