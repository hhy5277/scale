"""Tools needed ot Scale's API documentation"""

import inspect
import json
import os
import yaml

from django.conf import settings
from django.conf.urls import RegexURLPattern, RegexURLResolver
from scale.urls import urlpatterns

from batch.configuration.definition.batch_definition import BATCH_DEFINITION_SCHEMA
from ingest.scan.configuration.scan_configuration import SCAN_CONFIGURATION_SCHEMA
from ingest.strike.configuration.strike_configuration import STRIKE_CONFIGURATION_SCHEMA
from ingest.triggers.configuration.ingest_trigger_rule import INGEST_TRIGGER_SCHEMA
from job.configuration.interface.error_interface import ERROR_INTERFACE_SCHEMA
from job.configuration.interface.job_interface import JOB_INTERFACE_SCHEMA
from job.configuration.json.execution.exe_config import EXE_CONFIG_SCHEMA
from job.configuration.json.job.job_config import JOB_CONFIG_SCHEMA
from job.configuration.results.results_manifest.results_manifest import RESULTS_MANIFEST_SCHEMA
from node.resources.json.resources import RESOURCES_SCHEMA
from port.schema import CONFIGURATION_SCHEMA
from recipe.configuration.definition.recipe_definition import RECIPE_DEFINITION_SCHEMA
from source.triggers.configuration.parse_trigger_rule import PARSE_TRIGGER_SCHEMA
from storage.configuration.workspace_configuration import WORKSPACE_CONFIGURATION_SCHEMA


class BuildDocs():
    """Tools needed to generate Scale's API documentation

    BuildDocs depends on the following Scale elements to work properly:

    ==Schemas
        BATCH_DEFINITION_SCHEMA
        CONFIGURATION_SCHEMA
        ERROR_INTERFACE_SCHEMA
        EXE_CONFIG_SCHEMA
        INGEST_TRIGGER_SCHEMA
        JOB_CONFIG_SCHEMA
        JOB_INTERFACE_SCHEMA
        PARSE_TRIGGER_SCHEMA
        RECIPE_DEFINITION_SCHEMA
        RESOURCES_SCHEMA
        RESULTS_MANIFEST_SCHEMA
        SCAN_CONFIGURATION_SCHEMA
        STRIKE_CONFIGURATION_SCHEMA
        WORKSPACE_CONFIGURATION_SCHEMA

    ==Settings
        REST_FRAMEWORK (ALLOWED_VERSIONS, DEFAULT_VERSION)

    ==URLs
        scale.urls (urlpatterns)


    BuildDocs output description:
        blah blah blah
    """

    def __init__(self):
        """"""
        self.schama_map = {
            'batch_definition': BATCH_DEFINITION_SCHEMA,
            'configuration': CONFIGURATION_SCHEMA,
            'error_interface': ERROR_INTERFACE_SCHEMA,
            'exe_config': EXE_CONFIG_SCHEMA,
            'ingest_trigger': INGEST_TRIGGER_SCHEMA,
            'job_config': JOB_CONFIG_SCHEMA,
            'job_interface': JOB_INTERFACE_SCHEMA,
            'parse_trigger': PARSE_TRIGGER_SCHEMA,
            'recipe_definition': RECIPE_DEFINITION_SCHEMA,
            'resources': RESOURCES_SCHEMA,
            'results_manafest': RESULTS_MANIFEST_SCHEMA,
            'scan_configuration': SCAN_CONFIGURATION_SCHEMA,
            'strike_configuration': STRIKE_CONFIGURATION_SCHEMA,
            'workspace_configuration': WORKSPACE_CONFIGURATION_SCHEMA
        }

        self.generate_schemas()
        self.get_versions()
        self.get_urls()
        self.generate_paths()

    def alter_schemas(self):
        """Converts all schemas to YAML"""

        for schema_name, schema_definition in self.schama_map.items():
            self.schama_map[schema_name] = self._json_to_yaml(schema_name, schema_definition)

    def get_urls(self):
        """Pulls all needed urls out of Scale urls"""

        self.urls = {}

        def catch_url(urls):
            """Loops through the Scale urls and adds them to a dict"""
            for url in urls.url_patterns:
                if isinstance(url, RegexURLResolver):
                    catch_url(url)
                if isinstance(url, RegexURLPattern):
                    self.urls[url.name.replace('_', ' ').title()] = {
                        'pattern': url.regex.pattern,
                        'function': url.lookup_str
                    }

        for version in urlpatterns:
            if self.api_default in version.regex.pattern:
                catch_url(version)

    def get_versions(self):
        """Pulls all needed versions out of Scale settings"""

        self.api_default = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.api_versions = '` `'.join(list(settings.REST_FRAMEWORK['ALLOWED_VERSIONS']))

    def get_url_doc_strings(self):
        """Pulls out all needed Scale view doc strings"""

        scale_view_functions = [
            'create',
            'get',
            'list',
            'post',
            'patch',
            'retrieve'
        ]

        for name, properties in self.urls.items():
            module_name = properties['function'].rsplit('.', 1)
            module = __import__(module_name[0], globals(), locals(), [module_name[-1]], -1)
            module_method = getattr(module, module_name[-1])
            self.urls[name]['description'] = inspect.getdoc(module_method)

            self.urls[name]['endpoints'] = {}
            for endpoint, _v in module_method.__dict__.items():
                if endpoint in scale_view_functions:
                    self.urls[name]['endpoints'][endpoint] = inspect.getdoc(getattr(module_method, endpoint))

    def generate_paths(self):
        """Generates everything for paths"""

        self.get_url_doc_strings()

    def generate_schemas(self):
        """Generates everything for schemas"""

        self.alter_schemas()
        self.write_schemas()
        self.write_schema_index()

    def write_schema_index(self):
        """Creates a glue file that links all other schemas into one definition file"""

        glue = {}

        for key, _value in self.schama_map.items():
            glue[key] = '#'.join([self._generate_file_path(key, absolute_path=False), key])

        target = self._generate_file_path('index')

        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        with open(os.path.join(target), 'w') as file_out:
            file_out.write(yaml.dump(yaml.load(json.dumps(glue)), default_flow_style=False))

    def write_schemas(self):
        """Writes out YAML files for each schema"""

        for schema_name, schema_definition in self.schama_map.items():
            target = self._generate_file_path(schema_name)

            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))

            with open(os.path.join(target), 'w') as file_out:
                file_out.write(schema_definition)

    def _generate_file_path(self, schema_name, absolute_path=True):
        """Generates the absolute OR relative file path for a schema"""

        if absolute_path:
            actual_dir = os.path.dirname(os.path.abspath(__file__))
            target_dir = os.path.join(actual_dir, 'components')
        else:
            target_dir = '/'

        file_name = '.'.join([schema_name, 'yaml'])
        return os.path.join(target_dir, file_name)


    def _json_to_yaml(self, schema_name, schema):
        """Converts django json schema to swagger ingestable YAML"""

        obj_properties = schema['properties'] if 'properties' in schema else {}

        if 'definitions' in schema:
            obj_definitions = schema['definitions']
            for key, value in obj_properties.items():
                if 'items' in value:
                    if '$ref' in value['items']:
                        obj_properties[key]['items'] = obj_definitions[value['items']['$ref'].split('/')[-1]]
            schema['properties'] = obj_properties
            del schema['definitions']

        schema = {
            schema_name: schema
        }

        return yaml.dump(yaml.load(json.dumps(schema)), default_flow_style=False)


if __name__ == '__main__':
    BuildDocs()
        