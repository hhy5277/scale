from __future__ import unicode_literals

import django
from django.test import TestCase
from django.utils.timezone import now

from job.configuration.results.job_results import JobResults
from job.models import Job
from job.test import utils as job_test_utils
from recipe.messages.update_recipes import UpdateRecipes
from recipe.test import utils as recipe_test_utils
from storage.test import utils as storage_test_utils


class TestUpdateRecipes(TestCase):

    def setUp(self):
        django.setup()

    def test_json(self):
        """Tests coverting a UpdateRecipes message to and from JSON"""

        self.job_1_failed = job_test_utils.create_job(status='FAILED')
        self.job_1_pending = job_test_utils.create_job(status='PENDING')
        definition_1 = {
            'version': '1.0',
            'input_data': [],
            'jobs': [{
                'name': 'job_failed',
                'job_type': {
                    'name': self.job_1_failed.job_type.name,
                    'version': self.job_1_failed.job_type.version,
                },
            }, {
                'name': 'job_pending',
                'job_type': {
                    'name': self.job_1_pending.job_type.name,
                    'version': self.job_1_pending.job_type.version,
                },
                'dependencies': [{
                    'name': 'job_failed',
                }],
            }],
        }
        self.recipe_type_1 = recipe_test_utils.create_recipe_type_v6(definition=definition_1)
        self.recipe_1 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_1)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_1, job_name='job_failed', job=self.job_1_failed)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_1, job_name='job_pending', job=self.job_1_pending)

        self.job_2_running = job_test_utils.create_job(status='RUNNING')
        self.job_2_blocked = job_test_utils.create_job(status='BLOCKED')
        definition_2 = {
            'version': '1.0',
            'input_data': [],
            'jobs': [{
                'name': 'job_running',
                'job_type': {
                    'name': self.job_2_running.job_type.name,
                    'version': self.job_2_running.job_type.version,
                },
            }, {
                'name': 'job_blocked',
                'job_type': {
                    'name': self.job_2_blocked.job_type.name,
                    'version': self.job_2_blocked.job_type.version,
                },
                'dependencies': [{
                    'name': 'job_running',
                }],
            }],
        }
        self.recipe_type_2 = recipe_test_utils.create_recipe_type_v6(definition=definition_2)
        self.recipe_2 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_2)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_2, job_name='job_running', job=self.job_2_running)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_2, job_name='job_blocked', job=self.job_2_blocked)

        # Add recipes to message
        message = UpdateRecipes()
        if message.can_fit_more():
            message.add_recipe(self.recipe_1.id)
        if message.can_fit_more():
            message.add_recipe(self.recipe_2.id)

        # Convert message to JSON and back, and then execute
        message_json_dict = message.to_json()
        new_message = UpdateRecipes.from_json(message_json_dict)
        result = new_message.execute()

        self.assertTrue(result)
        self.assertEqual(len(new_message.new_messages), 2)
        for msg in new_message.new_messages:
            self.assertEqual(msg.type, 'update_recipe')

    def test_execute(self):
        """Tests calling UpdateRecipes.execute() successfully"""

        # Create recipes for testing the setting of jobs to BLOCKED/PENDING
        self.job_1_failed = job_test_utils.create_job(status='FAILED')
        self.job_1_pending = job_test_utils.create_job(status='PENDING')
        definition_1 = {
            'version': '1.0',
            'input_data': [],
            'jobs': [{
                'name': 'job_failed',
                'job_type': {
                    'name': self.job_1_failed.job_type.name,
                    'version': self.job_1_failed.job_type.version,
                },
            }, {
                'name': 'job_pending',
                'job_type': {
                    'name': self.job_1_pending.job_type.name,
                    'version': self.job_1_pending.job_type.version,
                },
                'dependencies': [{
                    'name': 'job_failed',
                }],
            }],
        }
        self.recipe_type_1 = recipe_test_utils.create_recipe_type_v6(definition=definition_1)
        self.recipe_1 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_1)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_1, job_name='job_failed', job=self.job_1_failed)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_1, job_name='job_pending', job=self.job_1_pending)

        self.job_2_running = job_test_utils.create_job(status='RUNNING')
        self.job_2_blocked = job_test_utils.create_job(status='BLOCKED')
        definition_2 = {
            'version': '1.0',
            'input_data': [],
            'jobs': [{
                'name': 'job_running',
                'job_type': {
                    'name': self.job_2_running.job_type.name,
                    'version': self.job_2_running.job_type.version,
                },
            }, {
                'name': 'job_blocked',
                'job_type': {
                    'name': self.job_2_blocked.job_type.name,
                    'version': self.job_2_blocked.job_type.version,
                },
                'dependencies': [{
                    'name': 'job_running',
                }],
            }],
        }
        self.recipe_type_2 = recipe_test_utils.create_recipe_type_v6(definition=definition_2)
        self.recipe_2 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_2)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_2, job_name='job_running', job=self.job_2_running)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_2, job_name='job_blocked', job=self.job_2_blocked)

        # Create recipe for testing the setting of input for a starting job in a recipe (no parents)
        input_name_1 = 'Test Input 1'
        output_name_1 = 'Test Output 1'
        interface_1 = {
            'version': '1.0',
            'command': 'my_cmd',
            'command_arguments': 'args',
            'input_data': [{
                'name': input_name_1,
                'type': 'file',
                'media_types': ['text/plain'],
            }],
            'output_data': [{
                'name': output_name_1,
                'type': 'files',
                'media_type': 'image/png',
            }],
        }
        job_type_3 = job_test_utils.create_job_type(interface=interface_1)
        job_3 = job_test_utils.create_job(job_type=job_type_3, status='PENDING', num_exes=0)

        input_name_2 = 'Test Input 2'
        output_name_2 = 'Test Output 2'
        interface_2 = {
            'version': '1.0',
            'command': 'my_cmd',
            'command_arguments': 'args',
            'input_data': [{
                'name': input_name_2,
                'type': 'files',
                'media_types': ['image/png', 'image/tiff'],
            }],
            'output_data': [{
                'name': output_name_2,
                'type': 'file',
            }],
        }
        job_type_4 = job_test_utils.create_job_type(interface=interface_2)
        job_4 = job_test_utils.create_job(job_type=job_type_4, status='PENDING', num_exes=0)
        workspace = storage_test_utils.create_workspace()
        file_1 = storage_test_utils.create_file(workspace=workspace, media_type='text/plain')

        definition = {
            'version': '1.0',
            'input_data': [{
                'name': 'Recipe Input',
                'type': 'file',
                'media_types': ['text/plain'],
            }],
            'jobs': [{
                'name': 'Job 1',
                'job_type': {
                    'name': job_type_3.name,
                    'version': job_type_3.version,
                },
                'recipe_inputs': [{
                    'recipe_input': 'Recipe Input',
                    'job_input': input_name_1,
                }]
            }, {
                'name': 'Job 2',
                'job_type': {
                    'name': job_type_4.name,
                    'version': job_type_4.version,
                },
                'dependencies': [{
                    'name': 'Job 1',
                    'connections': [{
                        'output': output_name_1,
                        'input': input_name_2,
                    }],
                }],
            }],
        }
        data = {
            'version': '1.0',
            'input_data': [{
                'name': 'Recipe Input',
                'file_id': file_1.id,
            }],
            'workspace_id': workspace.id,
        }
        self.recipe_type_3 = recipe_test_utils.create_recipe_type_v6(definition=definition)
        self.recipe_3 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_3, input=data)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_3, job_name='Job 1', job=job_3)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_3, job_name='Job 2', job=job_4)

        # Create recipe for testing the setting of input for a child job
        job_5 = job_test_utils.create_job(job_type=job_type_3, status='COMPLETED')
        file_2 = storage_test_utils.create_file(workspace=workspace, media_type='text/plain')
        job_5_output_dict = {
            'version': '1.0',
            'output_data': [{
                'name': output_name_1,
                'file_ids': [file_2.id]
            }]
        }
        job_test_utils.create_job_exe(job=job_5, output=JobResults(job_5_output_dict))
        # Complete job 5 and set its output so that update recipe message can give go ahead for child job 6
        Job.objects.process_job_output([job_5.id], now())
        job_6 = job_test_utils.create_job(job_type=job_type_4, status='PENDING', num_exes=0)
        self.recipe_4 = recipe_test_utils.create_recipe(recipe_type=self.recipe_type_3, input=data)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_4, job_name='Job 1', job=job_5)
        recipe_test_utils.create_recipe_job(recipe=self.recipe_4, job_name='Job 2', job=job_6)

        # Add recipes to message
        message = UpdateRecipes()
        if message.can_fit_more():
            message.add_recipe(self.recipe_1.id)
        if message.can_fit_more():
            message.add_recipe(self.recipe_2.id)
        if message.can_fit_more():
            message.add_recipe(self.recipe_3.id)
        if message.can_fit_more():
            message.add_recipe(self.recipe_4.id)

        # Execute message
        result = message.execute()
        self.assertTrue(result)

        self.assertEqual(len(message.new_messages), 4)
        for msg in message.new_messages:
            self.assertEqual(msg.type, 'update_recipe')

        # Test executing message again
        message_json_dict = message.to_json()
        message = UpdateRecipes.from_json(message_json_dict)
        result = message.execute()
        self.assertTrue(result)

        # Make sure the same messages are returned
        self.assertEqual(len(message.new_messages), 4)
        for msg in message.new_messages:
            self.assertEqual(msg.type, 'update_recipe')
