"""Defines the abstract base class for all system tasks"""
from __future__ import unicode_literals

from abc import ABCMeta

from django.conf import settings

from job.execution.configuration.docker_param import DockerParameter
from job.tasks.base_task import Task


class SystemTask(Task):
    """Abstract base class for a system task
    """

    __metaclass__ = ABCMeta

    def __init__(self, task_id, task_name):
        """Constructor

        :param task_id: The unique ID of the task
        :type task_id: string
        :param task_name: The name of the task
        :type task_name: string
        """

        super(SystemTask, self).__init__(task_id, task_name, None)

        self._uses_docker = True
        self._docker_image = self._create_scale_image_name()
        self._docker_params = []
        self._is_docker_privileged = False
        self._command = None
        self._command_arguments = None
        self._running_timeout_threshold = None

        # System task properties that sub-classes should override
        self.task_type = None
        self.title = task_name
        self.description = None

    def _add_database_docker_params(self):
        """Adds the necessary Docker parameters to this task to provide the Scale database connection settings
        """

        db_params = [DockerParameter('env', 'DATABASE_URL=%s' % settings.DATABASE_URL)]

        self._docker_params.extend(db_params)

    def _add_messaging_docker_params(self):
        """Adds the necessary Docker parameters to this task to provide the backend messaging connection settings
        """

        broker_url = settings.BROKER_URL
        queue_name = settings.QUEUE_NAME
        messaging_params = []

        if broker_url:
            messaging_params.append(DockerParameter('env', 'SCALE_BROKER_URL=%s' % broker_url))
        if queue_name:
            messaging_params.append(DockerParameter('env', 'SCALE_QUEUE_NAME=%s' % queue_name))

        self._docker_params.extend(messaging_params)
