from __future__ import unicode_literals

import django
from django.test import TestCase
from django.utils.timezone import now

import job.test.utils as job_test_utils
import recipe.test.utils as recipe_test_utils
import storage.test.utils as storage_test_utils
import trigger.test.utils as trigger_test_utils
from job.models import Job
from queue.models import Queue
from source.triggers.parse_trigger_handler import ParseTriggerHandler
from storage.models import ScaleFile


class TestParseTriggerHandlerProcessParsedSourceFile(TestCase):

    def setUp(self):
        django.setup()

        self.input_name = 'Test Input'
        self.output_name = 'Test Output'
        self.workspace = storage_test_utils.create_workspace()

        # This job trigger should not match due to a different media type
        job_trigger_config = {
            'version': '1.0',
            'condition': {
                'media_type': 'image/png',
            },
            'data': {
                'input_data_name': self.input_name,
                'workspace_name': self.workspace.name
            },
        }
        job_trigger_rule = trigger_test_utils.create_trigger_rule(configuration=job_trigger_config)

        interface_1 = {
            'version': '1.0',
            'command': 'my_cmd',
            'command_arguments': 'args',
            'input_data': [{
                'name': self.input_name,
                'type': 'file',
            }],
        }
        self.job_type_1 = job_test_utils.create_job_type(interface=interface_1, trigger_rule=job_trigger_rule)

        interface_2 = {
            'version': '1.0',
            'command': 'my_cmd',
            'command_arguments': 'args',
            'input_data': [{
                'name': self.input_name,
                'type': 'file',
            }],
            'output_data': [{
                'name': self.output_name,
                'type': 'file',
            }],
        }
        self.job_type_2 = job_test_utils.create_job_type(interface=interface_2, trigger_rule=job_trigger_rule)

        # create a recipe that runs both jobs
        definition_1 = {
            'version': '1.0',
            'input_data': [{
                'name': self.input_name,
                'type': 'file',
                'required': True,
            }],
            'jobs': [{
                'name': 'Job 2',
                'job_type': {
                    'name': self.job_type_2.name,
                    'version': self.job_type_2.version,
                },
                'recipe_inputs': [{
                    'recipe_input': self.input_name,
                    'job_input': self.input_name,
                }],
            }, {
                'name': 'Job 1',
                'job_type': {
                    'name': self.job_type_1.name,
                    'version': self.job_type_1.version,
                },
                'dependencies': [{
                    'name': 'Job 2',
                    'connections': [{
                        'output': self.output_name,
                        'input': self.input_name,
                    }],
                }],
            }],
        }

        self.when_parsed = now()
        self.file_name = 'my_file.txt'
        self.data_type = 'test_file_type'
        self.media_type = 'text/plain'
        self.source_file = ScaleFile.objects.create(file_name=self.file_name, file_type='SOURCE',
                                                    media_type=self.media_type, file_size=10, data_type=self.data_type,
                                                    file_path='the_path', workspace=self.workspace)
        self.source_file.add_data_type_tag('type1')
        self.source_file.add_data_type_tag('type2')
        self.source_file.add_data_type_tag('type3')
        self.source_file.parsed = now()

        recipe_trigger_config = {
            'version': '1.0',
            'condition': {
                'media_type': 'text/plain',
            },
            'data': {
                'input_data_name': self.input_name,
                'workspace_name': self.workspace.name
            },
        }
        self.trigger_rule = trigger_test_utils.create_trigger_rule(configuration=recipe_trigger_config)
        self.recipe_type_1 = recipe_test_utils.create_recipe_type(definition=definition_1,
                                                                  trigger_rule=self.trigger_rule)


    def test_successful_job_creation(self):
        """Tests successfully processing a parse that triggers job creation."""

        # Set up data
        configuration = {
            'version': '1.0',
            'condition': {
                'media_type': 'text/plain',
                'data_types': ['type1', 'type2'],
            },
            'data': {
                'input_data_name': self.input_name,
                'workspace_name': self.workspace.name
            },
        }
        rule_model = trigger_test_utils.create_trigger_rule(trigger_type='PARSE', configuration=configuration)
        self.job_type_1.trigger_rule = rule_model
        self.job_type_1.save()

        # Call method to test
        ParseTriggerHandler().process_parsed_source_file(self.source_file)

        # Check results
        queue_1 = Queue.objects.get(job_type=self.job_type_1.id)
        job_1 = Job.objects.get(pk=queue_1.job_id)
        self.assertEqual(job_1.input['input_data'][0]['name'], self.input_name)
        self.assertEqual(job_1.input['input_data'][0]['file_id'], self.source_file.id)

    def test_successful_recipe_creation(self):
        """Tests successfully processing a parse that triggers recipe creation."""

        # Set up data
        configuration = {
            'version': '1.0',
            'condition': {
                'media_type': 'text/plain',
            },
            'data': {
                'input_data_name': self.input_name,
                'workspace_name': self.workspace.name
            },
        }

        rule_model = trigger_test_utils.create_trigger_rule(trigger_type='PARSE', configuration=configuration)
        self.recipe_type_1.trigger_rule = rule_model
        self.recipe_type_1.save()

        # Call method to test
        ParseTriggerHandler().process_parsed_source_file(self.source_file)

        # Check results...ensure first job is queued
        queue_1 = Queue.objects.get(job_type=self.job_type_2.id)
        job_1 = Job.objects.get(pk=queue_1.job_id)
        self.assertEqual(job_1.input['input_data'][0]['name'], self.input_name)
        self.assertEqual(job_1.input['input_data'][0]['file_id'], self.source_file.id)
        self.assertEqual(job_1.input['output_data'][0]['name'], self.output_name)
        self.assertEqual(job_1.input['output_data'][0]['workspace_id'], self.workspace.id)
