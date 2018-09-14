# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-06-21 21:10


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('error', '0004_error_should_be_retried'),
    ]

    operations = [
        migrations.AddField(
            model_name='error',
            name='job_type_name',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='error',
            name='category',
            field=models.CharField(choices=[('SYSTEM', 'SYSTEM'), ('ALGORITHM', 'ALGORITHM'), ('DATA', 'DATA')], default='SYSTEM', max_length=50),
        ),
        migrations.AlterField(
            model_name='error',
            name='description',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
        migrations.AlterField(
            model_name='error',
            name='name',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name='error',
            unique_together=set([('job_type_name', 'name')]),
        ),
    ]
