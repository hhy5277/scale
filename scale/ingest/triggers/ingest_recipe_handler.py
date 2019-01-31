"""Defines the class that handles ingest trigger rules"""
from __future__ import unicode_literals

import logging

from django.db import transaction

from ingest.triggers.configuration.ingest_trigger_rule import IngestTriggerRuleConfiguration
from ingest.models import IngestEvent, Scan, Strike
from job.configuration.data.job_data import JobData
from job.models import JobType
from queue.models import Queue
from recipe.seed.recipe_data import RecipeData
from recipe.configuration.data.recipe_data import LegacyRecipeData
from recipe.models import RecipeType
from storage.models import Workspace
from trigger.handler import TriggerRuleHandler

logger = logging.getLogger(__name__)

RECIPE_TYPE = 'RECIPE'

# TODO:
# This was modeled off the IngestTriggerHandler class
# Do we need to inherit from an "IngestTriggerRule" ?
class IngestRecipeHandler(object):
    """Handles ingest trigger rules
    """

    def __init__(self):
        """Constructor
        """

        super(IngestRecipeHandler, self).__init__()#RECIPE_TYPE)

    # def create_configuration(self, config_dict):
    #     """See :meth:`trigger.handler.TriggerRuleHandler.create_configuration`
    #     """

    #     return IngestTriggerRuleConfiguration(RECIPE_TYPE, config_dict)

    @transaction.atomic
    def process_ingested_source_file(self, source, source_file, when):
        """Processes the given ingested source file by kicking off its recipe.
        All database changes are made in an atomic transaction.

        :param source: The strike that triggered the ingest
        :type scan: `object`

        :param source_file: The source file that was ingested
        :type source_file: :class:`source.models.SourceFile`
        :param when: When the source file was ingested
        :type when: :class:`datetime.datetime`
        """
        # Create the recipe handler associated with the ingest strike/scan
        source_recipe_config = source.configuration['recipe']
        recipe_name = source_recipe_config['name']
        recipe_version = source_recipe_config['version']

        # Create the recipe handler associated with the ingest strike/scan
        source_recipe_config = source.configuration['recipe']
        recipe_name = source_recipe_config['name']
        recipe_version = source_recipe_config['version']

        recipe_type = RecipeType.objects.get(name=recipe_name)
        if recipe_type:
            # Assuming one input per recipe, so pull the first defined input you find
            recipe_data = RecipeData({})
            input_name = recipe_type.get_definition().get_input_keys()[0]
            recipe_data.add_file_input(input_name, source_file.id)
            event = self._create_ingest_event(source, source_file, when)

            logger.info('Queuing new recipe of type %s %s', recipe_type.name, recipe_type.version)
            Queue.objects.queue_new_recipe_ingest_v6(recipe_type, recipe_data._new_data, event)
        else:
            logger.info('No recipe type found for %s %s' % (recipe_name, recipe_version))

    def _create_ingest_event(self, source, source_file, when):
        """Creates in the database and returns a trigger event model for the given ingested source file and recipe type

        :param source: The strike that triggered the ingest
        :type source: :class:`ingest.models.Strike`
        :param source_file: The source file that was ingested
        :type source_file: :class:`source.models.SourceFile`
        :param when: When the source file was ingested
        :type when: :class:`datetime.datetime`
        :returns: The new ingest event
        :rtype: :class:`ingest.models.IngestEvent`
        """

        description = {'version': '1.0', 'file_id': source_file.id, 'file_name': source_file.file_name}
        if type(source) is Strike:
            return IngestEvent.objects.create_strike_ingest_event(source, description, when)
        elif type(source) is Scan:
            return IngestEvent.objects.create_scan_ingest_event(source, description, when)
        else:
            logger.info('No valid source event for source file %s', source_file.file_name)