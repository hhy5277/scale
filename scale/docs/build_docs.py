"""Tools needed ot Scale's API documentation"""

import inspect
import json
import os
import pystache
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

    ==Views
        All swagger description and summary strings are pulled from Scale View docstrings.  There are three places
        that are checked and pulled:
            - Module docstring located at the top of each view.py file.
            - Class docstring located at the top of each view Class.
            - Method docstring located at the top of each function (function name must match scale_view_functions).

        Within each of those docstrings Markdown (github flavor) is supported.  Additionally, Method docstrings support
        several custom fields that help to populate the swagger docs. Those custom fields are:
            - paramaters - a JSON object
            - responses - a JSON object

        Example:_______________________________________________________________________________________________________

        def foo(bar):
            '''*This* is where you can put some markdown

            | foo | bar |
            |-----|-----|
            | like| this|

            _The five charater pattern `-*-*-` indicates that the description is over_

            Note: `parameters` and `responses` below need to be valid YAML
            -*-*-
            parameters:
              - name: username
                description: Foobar long description goes here
                required: true
                type: string
                paramType: form
              - name: password
                paramType: form
                required: true
                type: string

            responses:
                "200":
                  description: Everything went as expected
                  schema:
                    type: array
                    $ref: BATCH_DEFINITION_SCHEMA
                "204":
                  description: Created!
            -*-*-

            :param bar: Some silly param
            "param type: var
            '''
        ---------------------------------------------------------------------------------------------------------------


    BuildDocs output description:
        NotYetImplemented
    """

    def __init__(self):
        """Build docs"""

        self.mustache_file_name = 'index.mustache' # MUST ME IN SAME DIR AS THIS FILE

        self.api_default = settings.REST_FRAMEWORK['DEFAULT_VERSION']
        self.api_versions = ' '.join('`{0}`'.format(ver) for ver in list(settings.REST_FRAMEWORK['ALLOWED_VERSIONS']))

        self.component_map = {
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

        self.mustache_map = {
            'host': 'need_to_get_this_somewhow',
            'basepath': '.',
            'version': self.api_default,
            'openapi_version': '2.0'
        }
        self.path_map = {}
        self.tag_map = {}

        self.generate_paths()
        self.generate_components()
        self.write_index()

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
                    description = inspect.getdoc(getattr(module_method, endpoint))
                    self.path_map[name]['endpoints'][endpoint] = description

    def build_component_map(self):
        """Converts all components to pretty JSON"""

        for component_name, component_definition in self.component_map.items():
            self.component_map[component_name] = self._process_component_json(component_name, component_definition)

    def build_tag_map(self, path_map):
        """Builds a map for all tags with their descriptions."""

        tag_map = []
        for tag, tag_value in path_map.items():
            tag_map.append({
                'name': tag,
                'description': tag_value['description']
            })

        self.tag_map = tag_map

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
        self.write_paths()
        self.write_path_index()
        self.write_tags()

    def generate_components(self):
        """Generates everything for components"""

        self.build_component_map()
        self.write_components()
        self.write_component_index()

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

        self.path_map = {}
        for path_name, path_definition in new_path_map.items():
            self.path_map[path_name] = self._process_path_json(path_name, path_definition)

        # Construct the tag map before returning
        self.build_tag_map(new_path_map)

    def write_index(self):
        """Writes out the base JSON file for swagger"""

        target = self._generate_file_path('index')
        template_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.mustache_file_name)

        with open(template_file, 'r') as template_f:
            template = template_f.read()
            output = pystache.render(template, self.mustache_map)
            self._write_object(target, output)

    def write_paths(self):
        """Writes out JSON files for each path"""

        for path_name, path_definition in self.path_map.items():
            target = self._generate_file_path(path_name, 'paths')
            self._write_object(target, path_definition)

    def write_components(self):
        """Writes out JSON files for each component"""

        for component_name, component_definition in self.component_map.items():
            target = self._generate_file_path(component_name, 'components')
            self._write_object(target, component_definition)

    def write_path_index(self):
        """Creates a glue file that links all paths into one 'paths' file"""

        glue = {}

        for key, _value in self.path_map.items():
            glue[key] = '#' + self._generate_file_path(key, 'paths', absolute_path=False)

        target = self._generate_file_path('index', 'paths')
        self.mustache_map['paths_ref'] = target

        self._write_index(target, glue)

    def write_component_index(self):
        """Creates a glue file that links all components into one 'definition' file"""

        glue = {}

        for key, _value in self.component_map.items():
            glue[key] = '#'.join([self._generate_file_path(key, 'components', absolute_path=False), key])

        target = self._generate_file_path('index', 'components')
        self.mustache_map['definitions_ref'] = target

        self._write_index(target, glue)

    def write_tags(self):
        """Create a JSON file for the tags used in the paths."""

        target = self._generate_file_path('index', 'tags')
        self.mustache_map['tags_ref'] = target
        to_write = json.dumps(self.tag_map)
        self._write_object(target, to_write)

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

    @staticmethod
    def _generate_file_path(name, folder=None, absolute_path=True):
        """Generates the absolute OR relative file path for a file"""

        if absolute_path:
            target_dir = os.path.dirname(os.path.abspath(__file__))
            if folder:
                target_dir = os.path.join(target_dir, folder)
        else:
            target_dir = '/'

        file_name = '.'.join([name, 'json'])
        return os.path.join(target_dir, file_name)

    @staticmethod
    def _get_method_description(method_text):
        """Pulls out the markdown text that defines the method"""

        if method_text:
            descript = method_text.split('-*-*-')[0]
            descript.rstrip()
        else:
            descript = None

        return descript

    @staticmethod
    def _get_method_params(method_text):
        """Pulls out the YAML text that defines the method parameters and responses"""

        if method_text:
            text_split = method_text.split('-*-*-')
        else: 
            text_split = []

        params = None
        responses = None

        for string in text_split:
            try:
                yaml_dict = yaml.load(string)
                params = json.dumps(yaml_dict['parameters'])
                responses = json.dumps(yaml_dict['responses'])
            except (yaml.scanner.ScannerError, KeyError) as e:
                pass

        return params, responses

    def _process_path_json(self, path_name, path_definition):
        """Converts the constructed path_map to swagger ingestable JSON"""

        path = {path_name: {}}

        request_alias = {
            'list': 'get',
            'create': 'post'
        }

        if not path_definition['endpoints']:
            return {}

        for endpoint_name, endpoint_definiton in path_definition['endpoints'].items():
            if not endpoint_definiton['methods']:
                pass

            if endpoint_name in request_alias:
                endpoint_name = request_alias[endpoint_name]

            path[path_name][endpoint_name] = {}
            for method, method_info in endpoint_definiton['methods'].items():
                descript = self._get_method_description(method_info)
                params, responses = self._get_method_params(method_info)

                path[path_name][endpoint_name][method] = {}
                if descript:
                    path[path_name][endpoint_name][method]['description'] = descript
                if params:
                    path[path_name][endpoint_name][method]['parameters'] = params
                if responses:
                    path[path_name][endpoint_name][method]['responses'] = responses

                path[path_name][endpoint_name][method]['tags'] = [path_name]
                if 'function' in path_definition:
                    print path_definition['function']
                path[path_name][endpoint_name][method]['operationID'] = '.'.join([endpoint_definiton['function'],
                                                                                  method])

        for _name, content in path.items():
            return json.dumps(content)

    def _process_component_json(self, component_name, component):
        """Converts django json component to swagger ingestable JSON"""

        obj_properties = component['properties'] if 'properties' in component else {}

        if 'definitions' in component:
            obj_definitions = component['definitions']
            for key, value in obj_properties.items():
                if 'items' in value:
                    if '$ref' in value['items']:
                        obj_properties[key]['items'] = obj_definitions[value['items']['$ref'].split('/')[-1]]
            component['properties'] = obj_properties
            del component['definitions']

        component = {
            component_name: component
        }

        return json.dumps(component)

    @staticmethod
    def _write_index(target, json_dict):
        """Writes index files out to disk"""

        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        with open(os.path.join(target), 'w') as file_out:
            for _key, link in json_dict.items():
                file_out.write("'$ref': '%s'\n" % link)

    @staticmethod
    def _write_object(target, json_str):
        """Writes JSON out to disk"""

        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))

        with open(os.path.join(target), 'w') as file_out:
            file_out.write(json_str)

if __name__ == '__main__':
    BuildDocs()
