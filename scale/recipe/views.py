from __future__ import unicode_literals

import logging

import rest_framework.status as status
from django.db import transaction
from django.http.response import Http404, HttpResponse
from django.utils.timezone import now

from recipe.deprecation import RecipeDefinitionSunset
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

import util.rest as rest_util

from data.data.exceptions import InvalidData
from data.data.json.data_v6 import DataV6
from messaging.manager import CommandMessageManager
from job.models import Job, JobType
from queue.models import Queue
from recipe.configuration.data.exceptions import InvalidRecipeConnection, InvalidRecipeData
from recipe.configuration.definition.exceptions import InvalidDefinition as OldInvalidDefinition
from recipe.configuration.exceptions import InvalidRecipeConfiguration
from recipe.configuration.json.recipe_config_v6 import RecipeConfigurationV6
from recipe.definition.exceptions import InvalidDefinition
from recipe.definition.json.definition_v6 import RecipeDefinitionV6
from recipe.diff.exceptions import InvalidDiff
from recipe.diff.forced_nodes import ForcedNodes
from recipe.diff.json.forced_nodes_v6 import ForcedNodesV6
from recipe.messages.create_recipes import create_reprocess_messages
from recipe.models import Recipe, RecipeInputFile, RecipeType, RecipeTypeRevision
from recipe.serializers import (OldRecipeDetailsSerializer, RecipeDetailsSerializerV6,
                                RecipeSerializerV5, RecipeSerializerV6,
                                RecipeTypeDetailsSerializerV5, RecipeTypeDetailsSerializerV6,
                                RecipeTypeSerializerV5, RecipeTypeListSerializerV6,
                                RecipeTypeRevisionSerializerV6, RecipeTypeRevisionDetailsSerializerV6)
from storage.models import ScaleFile
from storage.serializers import ScaleFileSerializerV5, ScaleFileSerializerV6
from trigger.models import TriggerEvent
from util.rest import BadParameter, title_to_name


logger = logging.getLogger(__name__)


class RecipeTypesView(ListCreateAPIView):
    """This view is the endpoint for retrieving the list of all recipe types"""
    queryset = RecipeType.objects.all()

    def get_serializer_class(self):
        """Returns the appropriate serializer based off the requests version of the REST API. """

        if self.request.version == 'v6':
            return RecipeTypeListSerializerV6
        else:
            return RecipeTypeSerializerV5

    def list(self, request):
        """Retrieves the list of all recipe types and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self.list_v6(request)
        elif self.request.version == 'v5':
            return self.list_v5(request)

        raise Http404

    def list_v5(self, request):
        """Retrieves the list of all recipe types returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        started = rest_util.parse_timestamp(request, 'started', required=False)
        ended = rest_util.parse_timestamp(request, 'ended', required=False)
        rest_util.check_time_range(started, ended)

        order = rest_util.parse_string_list(request, 'order', ['name', 'version'])

        recipe_types = RecipeType.objects.get_recipe_types_v5(started, ended, order)

        page = self.paginate_queryset(recipe_types)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def list_v6(self, request):
        """Retrieves the list of all recipe types returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        keywords = rest_util.parse_string_list(request, 'keyword', required=False)
        is_active = rest_util.parse_bool(request, 'is_active', required=False)
        is_system = rest_util.parse_bool(request, 'is_system', required=False)
        order = ['name']

        recipe_types = RecipeType.objects.get_recipe_types_v6(keywords=keywords, is_active=is_active,
                                                     is_system=is_system, order=order)

        page = self.paginate_queryset(recipe_types)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request):
        """Creates a new recipe type and returns a link to the detail URL

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self._create_v6(request)
        elif self.request.version == 'v5':
            return self._create_v5(request)

        raise Http404

    def _create_v5(self, request):
        """Creates a new recipe type and returns a link to the detail URL

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        name = rest_util.parse_string(request, 'name')
        version = rest_util.parse_string(request, 'version')
        title = rest_util.parse_string(request, 'title', default_value=name)
        description = rest_util.parse_string(request, 'description', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition')

        try:
            with transaction.atomic():
                # Validate the recipe definition
                logger.info(definition_dict)
                recipe_def = RecipeDefinitionSunset.create(definition_dict)

                # Create the recipe type
                recipe_type = RecipeType.objects.create_recipe_type_v5(name, version, title, description, recipe_def,
                                                                    None)
        except (OldInvalidDefinition, InvalidRecipeConnection) as ex:
            logger.exception('Unable to create new recipe type: %s', name)
            raise BadParameter(unicode(ex))

        # Fetch the full recipe type with details
        try:
            recipe_type = RecipeType.objects.get_details_v5(recipe_type.id)
        except RecipeType.DoesNotExist:
            raise Http404

        url = reverse('recipe_type_id_details_view', args=[recipe_type.id], request=request)
        serializer = RecipeTypeDetailsSerializerV5(recipe_type)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=dict(location=url))

    def _create_v6(self, request):
        """Creates a new recipe type and returns a link to the detail URL

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        title = rest_util.parse_string(request, 'title', required=True)
        name = title_to_name(self.queryset, title)
        description = rest_util.parse_string(request, 'description', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition', required=True)

        try:
            with transaction.atomic():
                # Validate the recipe definition
                logger.info(definition_dict)
                recipe_def = RecipeDefinitionV6(definition=definition_dict, do_validate=True).get_definition()

                # Create the recipe type
                recipe_type = RecipeType.objects.create_recipe_type_v6(name, title, description, recipe_def)
        except InvalidDefinition as ex:
            logger.exception('Unable to create new recipe type: %s', name)
            raise BadParameter(unicode(ex))

        # Fetch the full recipe type with details
        try:
            recipe_type = RecipeType.objects.get_details_v6(recipe_type.name)
        except RecipeType.DoesNotExist:
            raise Http404

        url = reverse('recipe_type_details_view', args=[recipe_type.name], request=request)
        serializer = RecipeTypeDetailsSerializerV6(recipe_type)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=dict(location=url))


class RecipeTypeIDDetailsView(GenericAPIView):
    """This view is the endpoint for retrieving details of a recipe type"""
    queryset = RecipeType.objects.all()

    serializer_class = RecipeTypeDetailsSerializerV5

    def get(self, request, recipe_type_id):
        """Retrieves the details for a recipe type and return them in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_type_id: The id of the job type
        :type recipe_type_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        if self.request.version == 'v5':
            return self.get_v5(request, recipe_type_id)
        else:
            raise Http404

    def get_v5(self, request, recipe_type_id):
        """Retrieves the details for a recipe type and return them in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_type_id: The id of the recipe type
        :type recipe_type_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        try:
            recipe_type = RecipeType.objects.get_details_v5(recipe_type_id)
        except RecipeType.DoesNotExist:
            raise Http404

        # TODO: remove this check when REST API v5 is remmoved
        if self.request.version != 'v6':
            for jt in recipe_type.job_types:
                if jt.is_seed_job_type():
                    jt.manifest = JobType.objects.convert_manifest_to_v5_interface(jt.manifest)

        serializer = self.get_serializer(recipe_type)
        return Response(serializer.data)

    def patch(self, request, recipe_type_id):
        """Edits an existing job type and returns the updated details

        :param request: the HTTP PATCH request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_type_id: The ID for the job type.
        :type recipe_type_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v5':
            return self.patch_v5(request, recipe_type_id)
        else:
            raise Http404

    def patch_v5(self, request, recipe_type_id):
        """Edits an existing recipe type and returns the updated details

        :param request: the HTTP PATCH request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_type_id: The ID for the recipe type.
        :type recipe_type_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        title = rest_util.parse_string(request, 'title', required=False)
        description = rest_util.parse_string(request, 'description', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition', required=False)

        # Fetch the current recipe type model
        try:
            recipe_type = RecipeType.objects.get(pk=recipe_type_id)
        except RecipeType.DoesNotExist:
            raise Http404

        try:
            with transaction.atomic():
                # Validate the recipe definition
                recipe_def = None
                if definition_dict:
                    recipe_def = RecipeDefinitionSunset.create(definition_dict)

                # Edit the recipe type
                RecipeType.objects.edit_recipe_type_v5(recipe_type_id, title, description, recipe_def, None,
                                                    None)
        except (OldInvalidDefinition, InvalidDefinition,
                InvalidRecipeConnection) as ex:
            logger.exception('Unable to update recipe type: %i', recipe_type_id)
            raise BadParameter(unicode(ex))

        # Fetch the full recipe type with details
        try:
            recipe_type = RecipeType.objects.get_details_v5(recipe_type_id)
        except RecipeType.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(recipe_type)
        return Response(serializer.data)


class RecipeTypeDetailsView(GenericAPIView):
    """This view is the endpoint for retrieving details of a recipe type"""
    queryset = RecipeType.objects.all()

    serializer_class = RecipeTypeDetailsSerializerV6

    def get(self, request, name):
        """Retrieves the details for a recipe type and return them in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self.get_v6(request, name)
        else:
            raise Http404

    def get_v6(self, request, name):
        """Retrieves the details for a recipe type and return them in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        try:
            recipe_type = RecipeType.objects.get_details_v6(name)
        except RecipeType.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(recipe_type)
        return Response(serializer.data)

    def patch(self, request, name):
        """Edits an existing recipe type and returns the updated details

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self.patch_v6(request, name)
        else:
            raise Http404

    def patch_v6(self, request, name):
        """Edits an existing recipe type and returns the updated details

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        title = rest_util.parse_string(request, 'title', required=False)
        description = rest_util.parse_string(request, 'description', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition', required=False)
        auto_update = rest_util.parse_bool(request, 'auto_update', required=False)

        # Fetch the current recipe type model
        try:
            recipe_type = RecipeType.objects.filter(name=name).first()
        except RecipeType.DoesNotExist:
            raise Http404

        try:
            with transaction.atomic():
                # Validate the recipe definition
                recipe_def = None
                if definition_dict:
                    recipe_def = RecipeDefinitionV6(definition=definition_dict, do_validate=True).get_definition()

                # Edit the recipe type
                RecipeType.objects.edit_recipe_type_v6(recipe_type_id=recipe_type.id, title=title,
                                                       description=description, definition=recipe_def,
                                                       auto_update=auto_update)
        except InvalidDefinition as ex:
            logger.exception('Unable to update recipe type: %s', name)
            raise BadParameter(unicode(ex))

        return HttpResponse(status=204)

class RecipeTypeRevisionsView(ListAPIView):
    """This view is the endpoint for retrieving the list of all recipe types"""
    queryset = RecipeType.objects.all()

    serializer_class = RecipeTypeRevisionSerializerV6

    def list(self, request, name):
        """Retrieves the list of all recipe type revisions and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self.list_v6(request, name)
        else:
            raise Http404

    def list_v6(self, request, name):
        """Retrieves the list of all recipe type revisions returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        recipe_type_revs = RecipeTypeRevision.objects.get_revisions(name=name)

        page = self.paginate_queryset(recipe_type_revs)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

class RecipeTypeRevisionDetailsView(ListAPIView):
    """This view is the endpoint for retrieving the list of all recipe types"""
    queryset = RecipeType.objects.all()

    serializer_class = RecipeTypeRevisionDetailsSerializerV6

    def get(self, request, name, revision_num):
        """Retrieves the list of all recipe type revisions and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :param revision_num: The revision number of the job type
        :type revision_num: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self.get_v6(request, name, revision_num)
        else:
            raise Http404

    def get_v6(self, request, name, revision_num):
        """Retrieves the list of all recipe type revisions returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param name: The name of the recipe type
        :type name: string
        :param revision_num: The revision number of the job type
        :type revision_num: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        try:
            recipe_type_rev = RecipeTypeRevision.objects.get_revision(name, revision_num)
        except RecipeTypeRevision.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(recipe_type_rev)
        return Response(serializer.data)

class RecipeTypesValidationView(APIView):
    """This view is the endpoint for validating a new recipe type before attempting to actually create it"""
    queryset = RecipeType.objects.all()

    def post(self, request):
        """Validates a new recipe type and returns any warnings discovered

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if self.request.version == 'v6':
            return self._post_v6(request)
        elif self.request.version == 'v5':
            return self._post_v5(request)

        raise Http404

    def _post_v5(self, request):
        """Validates a new recipe type and returns any warnings discovered

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        name = rest_util.parse_string(request, 'name')
        version = rest_util.parse_string(request, 'version')
        title = rest_util.parse_string(request, 'title', default_value=name)
        description = rest_util.parse_string(request, 'description', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition')

        # Validate the recipe definition
        try:
            recipe_def = RecipeDefinitionSunset.create(definition_dict)
            warnings = RecipeType.objects.validate_recipe_type_v5(name, title, version, description, recipe_def,
                                                               None)
        except (OldInvalidDefinition, InvalidRecipeConnection) as ex:
            logger.exception('Unable to validate new recipe type: %s', name)
            raise BadParameter(unicode(ex))

        results = [{'id': w.key, 'details': w.details} for w in warnings]
        return Response({'warnings': results})

    def _post_v6(self, request):
        """Validates a new recipe type and returns any warnings discovered

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        name = rest_util.parse_string(request, 'name', required=False)
        definition_dict = rest_util.parse_dict(request, 'definition')

        # Validate the recipe definition
        validation = RecipeType.objects.validate_recipe_type_v6(name=name, definition_dict=definition_dict)

        resp_dict = {'is_valid': validation.is_valid, 'errors': [e.to_dict() for e in validation.errors],
                     'warnings': [w.to_dict() for w in validation.warnings], 'diff': validation.diff}
        return Response(resp_dict)


class RecipesView(ListAPIView):
    """This view is the endpoint for retrieving the list of all recipes"""
    queryset = Recipe.objects.all()

    def get_serializer_class(self):
        """Returns the appropriate serializer based off the requests version of the REST API. """

        if self.request.version == 'v6':
            return RecipeSerializerV6
        else:
            return RecipeSerializerV5

    def list(self, request):
        """Retrieves the list of all recipes and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        if request.version == 'v6':
            return self._list_v6(request)
        elif request.version == 'v5':
            return self._list_v5(request)

        raise Http404()

    def _list_v6(self, request):
        """Retrieves the list of all recipes and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        started = rest_util.parse_timestamp(request, 'started', required=False)
        ended = rest_util.parse_timestamp(request, 'ended', required=False)
        rest_util.check_time_range(started, ended)

        source_started = rest_util.parse_timestamp(request, 'source_started', required=False)
        source_ended = rest_util.parse_timestamp(request, 'source_ended', required=False)
        rest_util.check_time_range(source_started, source_ended)
        source_sensor_classes = rest_util.parse_string_list(request, 'source_sensor_class', required=False)
        source_sensors = rest_util.parse_string_list(request, 'source_sensor', required=False)
        source_collections = rest_util.parse_string_list(request, 'source_collection', required=False)
        source_tasks = rest_util.parse_string_list(request, 'source_task', required=False)

        recipe_ids = rest_util.parse_int_list(request, 'recipe_id', required=False)
        type_ids = rest_util.parse_int_list(request, 'recipe_type_id', required=False)
        type_names = rest_util.parse_string_list(request, 'recipe_type_name', required=False)
        batch_ids = rest_util.parse_int_list(request, 'batch_id', required=False)
        is_superseded = rest_util.parse_bool(request, 'is_superseded', required=False)
        is_completed = rest_util.parse_bool(request, 'is_completed', required=False)
        order = rest_util.parse_string_list(request, 'order', required=False)

        recipes = Recipe.objects.get_recipes_v6(started=started, ended=ended,
                                             source_started=source_started, source_ended=source_ended,
                                             source_sensor_classes=source_sensor_classes, source_sensors=source_sensors,
                                             source_collections=source_collections, source_tasks=source_tasks,
                                             ids=recipe_ids, type_ids=type_ids, type_names=type_names,
                                             batch_ids=batch_ids, is_superseded=is_superseded,
                                             is_completed=is_completed, order=order)

        page = self.paginate_queryset(recipes)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def _list_v5(self, request):
        """Retrieves the list of all recipes and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        started = rest_util.parse_timestamp(request, 'started', required=False)
        ended = rest_util.parse_timestamp(request, 'ended', required=False)
        rest_util.check_time_range(started, ended)

        type_ids = rest_util.parse_int_list(request, 'type_id', required=False)
        type_names = rest_util.parse_string_list(request, 'type_name', required=False)
        batch_ids = rest_util.parse_int_list(request, 'batch_id', required=False)
        include_superseded = rest_util.parse_bool(request, 'include_superseded', required=False)
        order = rest_util.parse_string_list(request, 'order', required=False)

        recipes = Recipe.objects.get_recipes_v5(started=started, ended=ended, type_ids=type_ids, type_names=type_names,
                                             batch_ids=batch_ids, include_superseded=include_superseded, order=order)

        page = self.paginate_queryset(recipes)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def post(self, request):
        """Queue a recipe and returns the new job information in JSON form

        :param request: the HTTP POST request
        :type request: :class:`rest_framework.request.Request`
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """
        if request.version != 'v6':
            raise Http404

        recipe_type_id = rest_util.parse_int(request, 'recipe_type_id')
        recipe_data = rest_util.parse_dict(request, 'input', {})
        configuration_dict = rest_util.parse_dict(request, 'configuration', required=False)
        configuration = None

        try:
            recipeData = DataV6(recipe_data, do_validate=True)
        except InvalidData as ex:
            logger.exception('Unable to queue new recipe. Invalid input: %s', recipe_data)
            raise BadParameter(unicode(ex))

        try:
            recipe_type = RecipeType.objects.get(pk=recipe_type_id)
        except RecipeType.DoesNotExist:
            raise Http404

        if configuration_dict:
            try:
                configuration = RecipeConfigurationV6(configuration_dict, do_validate=True).get_configuration()
            except InvalidRecipeConfiguration as ex:
                message = 'Recipe configuration invalid'
                logger.exception(message)
                raise BadParameter('%s: %s' % (message, unicode(ex)))

        try:
            recipe = Queue.objects.queue_new_recipe_for_user_v6(recipe_type, recipeData.get_data(), recipe_config=configuration)
        except InvalidRecipeData as err:
            return Response('Invalid recipe data: ' + unicode(err), status=status.HTTP_400_BAD_REQUEST)

        serializer = RecipeSerializerV6(recipe)
        recipe_url = reverse('recipe_details_view', args=[recipe.id], request=request)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=dict(location=recipe_url))


class RecipeDetailsView(RetrieveAPIView):
    """This view is the endpoint for retrieving details of a recipe"""
    queryset = Recipe.objects.all()

    # TODO: remove this class and un-comment the serializer declaration when REST API v5 is removed
    # serializer_class = RecipeDetailsSerializer
    def get_serializer_class(self):
        """Returns the appropriate serializer based off the requests version of the REST API. """

        if self.request.version == 'v6':
            return RecipeDetailsSerializerV6
        else:
            return OldRecipeDetailsSerializer

    def retrieve(self, request, recipe_id):
        """Retrieves the details for a recipe and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if request.version == 'v6':
            return self._retrieve_v6(request, recipe_id)
        elif request.version == 'v5':
            return self._retrieve_v5(request, recipe_id)

        raise Http404()

    def _retrieve_v5(self, request, recipe_id):
        """Retrieves the details for a recipe and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        try:
            recipe = Recipe.objects.get_details_v5(recipe_id)
        except Recipe.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(recipe)
        return Response(serializer.data)

    def _retrieve_v6(self, request, recipe_id):
        """Retrieves the details for a recipe and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        try:
            recipe = Recipe.objects.get_details(recipe_id)
        except Recipe.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(recipe)
        return Response(serializer.data)

class RecipeInputFilesView(ListAPIView):
    """This is the endpoint for retrieving details about input files associated with a given recipe."""
    queryset = RecipeInputFile.objects.all()

    def get_serializer_class(self):
        """Returns the appropriate serializer based off the requests version of the REST API. """

        if self.request.version == 'v6':
            return ScaleFileSerializerV6
        else:
            return ScaleFileSerializerV5

    def get(self, request, recipe_id):
        """Retrieve detailed information about the input files for a recipe

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The ID for the recipe.
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if request.version == 'v6':
            return self._get_v6(request, recipe_id)
        elif request.version == 'v5':
            return self._get_v5(request, recipe_id)

        raise Http404()

    def _get_v5(self, request, recipe_id):
        """Retrieve detailed information about the input files for a recipe

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The ID for the recipe.
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        started = rest_util.parse_timestamp(request, 'started', required=False)
        ended = rest_util.parse_timestamp(request, 'ended', required=False)
        rest_util.check_time_range(started, ended)
        time_field = rest_util.parse_string(request, 'time_field', required=False,
                                            accepted_values=ScaleFile.VALID_TIME_FIELDS)
        file_name = rest_util.parse_string(request, 'file_name', required=False)
        recipe_input = rest_util.parse_string(request, 'recipe_input', required=False)

        files = RecipeInputFile.objects.get_recipe_input_files(recipe_id, started=started, ended=ended,
                                                               time_field=time_field, file_name=file_name,
                                                               recipe_input=recipe_input)

        page = self.paginate_queryset(files)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def _get_v6(self, request, recipe_id):
        """Retrieve detailed information about the input files for a recipe

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The ID for the recipe.
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        started = rest_util.parse_timestamp(request, 'started', required=False)
        ended = rest_util.parse_timestamp(request, 'ended', required=False)
        rest_util.check_time_range(started, ended)
        time_field = rest_util.parse_string(request, 'time_field', required=False,
                                            accepted_values=ScaleFile.VALID_TIME_FIELDS)
        file_name = rest_util.parse_string(request, 'file_name', required=False)
        recipe_input = rest_util.parse_string(request, 'recipe_input', required=False)

        files = RecipeInputFile.objects.get_recipe_input_files(recipe_id, started=started, ended=ended,
                                                               time_field=time_field, file_name=file_name,
                                                               recipe_input=recipe_input)

        page = self.paginate_queryset(files)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class RecipeReprocessView(GenericAPIView):
    """This view is the endpoint for scheduling a reprocess of a recipe"""
    queryset = Recipe.objects.all()

    # TODO: remove this class and un-comment the serializer declaration when REST API v5 is removed
    # serializer_class = RecipeDetailsSerializer
    def get_serializer_class(self):
        """Returns the appropriate serializer based off the requests version of the REST API. """

        if self.request.version == 'v6':
            return RecipeDetailsSerializerV6
        else:
            return OldRecipeDetailsSerializer

    def post(self, request, recipe_id):
        """Schedules a recipe for reprocessing and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        if request.version == 'v6':
            return self._post_v6(request, recipe_id)
        elif request.version == 'v5':
            return self._post_v5(request, recipe_id)

        raise Http404()

    def _post_v5(self, request, recipe_id):
        """Schedules a recipe for reprocessing and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        job_names = rest_util.parse_string_list(request, 'job_names', required=False)
        all_jobs = rest_util.parse_bool(request, 'all_jobs', required=False)
        priority = rest_util.parse_int(request, 'priority', required=False)

        try:
            recipe = Recipe.objects.select_related('recipe_type', 'recipe_type_rev').get(id=recipe_id)
        except Recipe.DoesNotExist:
            raise Http404
        if recipe.is_superseded:
            raise BadParameter('Cannot reprocess a superseded recipe')
        event = TriggerEvent.objects.create_trigger_event('USER', None, {'user': 'Anonymous'}, now())
        root_recipe_id = recipe.root_superseded_recipe_id if recipe.root_superseded_recipe_id else recipe.id
        recipe_type_name = recipe.recipe_type.name
        revision_num = recipe.recipe_type_rev.revision_num
        forced_nodes = ForcedNodes()
        if all_jobs:
            forced_nodes.set_all_nodes()
        elif job_names:
            for job_name in job_names:
                forced_nodes.add_node(job_name)

        # Execute all of the messages to perform the reprocess
        messages = create_reprocess_messages([root_recipe_id], recipe_type_name, revision_num, event.id,
                                             forced_nodes=forced_nodes)
        while messages:
            msg = messages.pop(0)
            result = msg.execute()
            if not result:
                raise Exception('Reprocess failed on message type \'%s\'' % msg.type)
            messages.extend(msg.new_messages)

        # Update job priorities
        if priority is not None:
            Job.objects.filter(event_id=event.id).update(priority=priority)
            from queue.models import Queue
            Queue.objects.filter(job__event_id=event.id).update(priority=priority)

        new_recipe = Recipe.objects.get(root_superseded_recipe_id=root_recipe_id, is_superseded=False)
        try:
            new_recipe = Recipe.objects.get_details_v5(new_recipe.id)
        except Recipe.DoesNotExist:
            raise Http404

        serializer = self.get_serializer(new_recipe)

        url = reverse('recipe_details_view', args=[new_recipe.id], request=request)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=dict(location=url))

    def _post_v6(self, request, recipe_id):
        """Schedules a recipe for reprocessing and returns it in JSON form

        :param request: the HTTP GET request
        :type request: :class:`rest_framework.request.Request`
        :param recipe_id: The id of the recipe
        :type recipe_id: int encoded as a str
        :rtype: :class:`rest_framework.response.Response`
        :returns: the HTTP response to send back to the user
        """

        forced_nodes_json = rest_util.parse_dict(request, 'forced_nodes', required=True)

        try:
            forced_nodes = ForcedNodesV6(forced_nodes_json, do_validate=True)
        except InvalidDiff as ex:
            logger.exception('Unable to reprocess recipe. Invalid input: %s', forced_nodes_json)
            raise BadParameter(unicode(ex))

        try:
            recipe = Recipe.objects.select_related('recipe_type', 'recipe_type_rev').get(id=recipe_id)
        except Recipe.DoesNotExist:
            raise Http404
        if recipe.is_superseded:
            raise BadParameter('Cannot reprocess a superseded recipe')

        validation = recipe.recipe_type_rev.validate_forced_nodes(forced_nodes_json)
        if not validation.is_valid:
            raise BadParameter('Unable to reprocess recipe. Errors in validating forced_nodes: %s' % validation.errors)

        if validation.warnings:
            logger.warning('Warnings encountered when reprocessing: %s' % validation.warnings)

        event = TriggerEvent.objects.create_trigger_event('USER', None, {'user': 'Anonymous'}, now())
        root_recipe_id = recipe.root_superseded_recipe_id if recipe.root_superseded_recipe_id else recipe.id
        recipe_type_name = recipe.recipe_type.name
        revision_num = recipe.recipe_type_rev.revision_num

        # Execute all of the messages to perform the reprocess
        messages = create_reprocess_messages([root_recipe_id], recipe_type_name, revision_num, event.id,
                                             forced_nodes=forced_nodes.get_forced_nodes())

        CommandMessageManager().send_messages(messages)

        return Response(status=status.HTTP_202_ACCEPTED)