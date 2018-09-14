# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('trigger', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='triggerrule',
            name='is_active',
            field=models.BooleanField(default=True, db_index=True),
            preserve_default=True,
        ),
    ]
