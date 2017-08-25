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
        NotYetImplemented
    """

    def __init__(self):
        """Build docs"""

        self.api_default = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.api_versions = '` `'.join(list(settings.REST_FRAMEWORK['ALLOWED_VERSIONS']))

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

        self.path_map = {}

        self.generate_paths()
        self.generate_schemas()

    def build_path_map(self):
        """Pulls out all needed Scale view doc strings"""

        scale_view_functions = [
            'create',
            'get',
            'list',
            'post',
            'patch',
            'retrieve'
        ]

        for name, properties in self.path_map.items():
            module_name = properties['function'].rsplit('.', 1)
            module = __import__(module_name[0], globals(), locals(), [module_name[-1]], -1)
            module_method = getattr(module, module_name[-1])
            self.path_map[name]['description'] = inspect.getdoc(module_method)
            self.path_map[name]['global_description'] = inspect.getdoc(module)

            self.path_map[name]['endpoints'] = {}
            for endpoint, _v in module_method.__dict__.items():
                if endpoint in scale_view_functions:
                    description = self._fix_path_description(inspect.getdoc(getattr(module_method, endpoint)))
                    self.path_map[name]['endpoints'][endpoint] = description

    def build_schema_map(self):
        """Converts all schemas to YAML"""

        for schema_name, schema_definition in self.schama_map.items():
            self.schama_map[schema_name] = self._schema_json_to_yaml(schema_name, schema_definition)

    def get_paths(self):
        """Pulls all needed urls out of Scale urls"""

        def catch_url(urls):
            """Loops through the Scale urls and adds them to a dict"""
            for url in urls.url_patterns:
                if isinstance(url, RegexURLResolver):
                    catch_url(url)
                if isinstance(url, RegexURLPattern):
                    self.path_map[url.name.replace('_', ' ').title()] = {
                        'pattern': self._fix_path_pattern(url.regex.pattern),
                        'function': url.lookup_str
                    }

        for version in urlpatterns:
            if self.api_default in version.regex.pattern:
                catch_url(version)

    def generate_paths(self):
        """Generates everything for paths"""

        self.get_paths()
        self.build_path_map()
        self.optimize_path_map()
        print json.dumps(self.path_map)
        #self.write_paths()
        #self.write_path_index()

        # for path_name, path_definition in self.path_map.items():
        #     self.path_map[path_name] = self._path_json_to_yaml(path_name, path_definition)

    def generate_schemas(self):
        """Generates everything for schemas"""

        self.build_schema_map()
        self.write_schemas()
        self.write_schema_index()

    def optimize_path_map(self):
        """Reorganize something we just made to ease swagger doc generation"""

        new_path_map = {}

        for view, description in self.path_map.items():
            new_index = description['function'].split('.')[0]

            if new_index not in new_path_map:
                new_path_map[new_index] = {}
                new_path_map[new_index]['endpoints'] = {}
                new_path_map[new_index]['description'] = description['global_description']

            new_path_map[new_index]['endpoints'][description['pattern']] = {}

            new_path_map[new_index]['endpoints'][description['pattern']]['description'] = description['description']
            new_path_map[new_index]['endpoints'][description['pattern']]['function'] = description['function']
            new_path_map[new_index]['endpoints'][description['pattern']]['pretty_name'] = view
            new_path_map[new_index]['endpoints'][description['pattern']]['methods'] = {}

            for request, summary in description['endpoints'].items():
                new_path_map[new_index]['endpoints'][description['pattern']]['methods'][request] = summary

        self.path_map = new_path_map

    def write_paths(self):
        """Writes out YAML files for each path"""

        for _path_name, path_definition in self.path_map.items():
            if path_definition:
                path_group = path_definition['pattern'].split('/')[0]
                target = self._generate_file_path(path_group, 'paths')

                if not os.path.isdir(os.path.dirname(target)):
                    os.makedirs(os.path.dirname(target))

                with open(os.path.join(target), 'w') as file_out:
                    file_out.write(path_definition)

    def write_schemas(self):
        """Writes out YAML files for each schema"""

        for schema_name, schema_definition in self.schama_map.items():
            target = self._generate_file_path(schema_name, 'components')

            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))

            with open(os.path.join(target), 'w') as file_out:
                file_out.write(schema_definition)

    def write_path_index(self):
        """Creates a glue file that links all paths into one 'paths' file"""

        pass

    def write_schema_index(self):
        """Creates a glue file that links all schemas into one 'definition' file"""

        glue = {}

        for key, _value in self.schama_map.items():
            glue[key] = '#'.join([self._generate_file_path(key, 'components', absolute_path=False), key])

        target = self._generate_file_path('index', 'components')

        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        with open(os.path.join(target), 'w') as file_out:
            file_out.write(yaml.dump(yaml.load(json.dumps(glue)), default_flow_style=False))

    @staticmethod
    def _fix_path_description(description):
        """Fixes the doc strings to be more friendly on the eyes (and swagger)"""

        if not description:
            return ''

        description = description.split(':param')[0]
        description = description.rstrip()

        return description

    @staticmethod
    def _fix_path_pattern(pattern):
        """Fixes the regex strings to be more friendly on the eyes (and swagger)"""

        things_to_replace = {
            'metrics/([\\w-]+)': 'metrics/{metric_name}',
            '(stdout|stderr|combined)': '{log_type}',
            '^': '',
            '$': '',
            '(?P<': '{',
            '>\\d+)': '}',
            '>[\\w.]{0,250})': '}',
            '(\\d+)': '{id}'
        }

        for old, new in things_to_replace.items():
            pattern = pattern.replace(old, new)

        return pattern

    def _generate_file_path(self, name, folder, absolute_path=True):
        """Generates the absolute OR relative file path for a file"""

        if absolute_path:
            actual_dir = os.path.dirname(os.path.abspath(__file__))
            target_dir = os.path.join(actual_dir, folder)
        else:
            target_dir = '/'

        file_name = '.'.join([name, 'yaml'])
        return os.path.join(target_dir, file_name)


    def _path_json_to_yaml(self, path_name, path_definition):
        """Converts the constructed path_map to swagger ingestable YAML"""

        request_alias = {
            'list': 'get',
            'create': 'post'
        }

        if not path_definition['endpoints']:
            return {}

        for endpoint_name, endpoint_definiton in path_definition['endpoints'].items():
            if endpoint_name in request_alias:
                endpoint_name = request_alias[endpoint_name]

    def _schema_json_to_yaml(self, schema_name, schema):
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
        