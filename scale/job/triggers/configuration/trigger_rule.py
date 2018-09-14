"""Defines the base configuration class for a trigger rule that triggers job creation"""


from abc import ABCMeta, abstractmethod

from trigger.configuration.trigger_rule import TriggerRuleConfiguration


class JobTriggerRuleConfiguration(TriggerRuleConfiguration, metaclass=ABCMeta):
    """The base class that represents trigger rule configurations that can create jobs when triggered
    """

    @abstractmethod
    def validate_trigger_for_job(self, job_interface):
        """Validates the trigger rule configuration to ensure it correctly connects with the given job type interface

        :param job_interface: The job type interface
        :type job_interface: :class:`job.configuration.interface.job_interface.JobInterface`
        :returns: A list of warnings discovered during validation
        :rtype: list[:class:`job.configuration.data.job_data.ValidationWarning`]

        :raises :class:`job.configuration.data.exceptions.InvalidConnection`: If the trigger rule connection to the job
            type interface is not valid
        """

        raise NotImplementedError()
