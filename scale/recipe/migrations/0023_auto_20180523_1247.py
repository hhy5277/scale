# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2018-05-23 12:47


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recipe', '0022_auto_20180307_1617'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='RecipeJob',
            new_name='RecipeNode',
        ),
        migrations.AlterModelTable(
            name='recipenode',
            table='recipe_node',
        ),
    ]
