"""Defines utility exceptions"""
from util.validation import ValidationError


class FileDoesNotExist(Exception):
    """Exception indicating an attempt was made to access a file that no longer exists
    """

    pass


class InvalidBrokerUrl(Exception):
    """Exception indicating the broker URL does not meet the format requirements"""

    pass


class ServiceAccountAuthFailure(Exception):
    """Exception indicating failure of request to login or communicate with DCOS using service account"""

    pass


class InvalidAWSCredentials(Exception):
    """Exception indicating missing credentials required to successfully authenticate to AWS"""

    pass


class RollbackTransaction(Exception):
    """Exception that can be thrown and swallowed to explicitly rollback a transaction"""

    pass


class ScaleLogicBug(Exception):
    """Exception that indicates a critical Scale logic bug has occurred"""

    pass


class TerminatedCommand(Exception):
    """Exception that can be thrown to indicate that a Scale command recieved a SIGTERM signal"""

    pass


class UnbalancedBrackets(Exception):
    """Exception thrown when a string is provided that contains unbalanced curly brackets"""

    pass


class ValidationException(Exception):
    """Exception indicating there was a validation error
    """

    def __init__(self, name, description):
        """Constructor

        :param name: The name of the validation error
        :type name: string
        :param description: The description of the validation error
        :type description: string
        """

        super(ValidationException, self).__init__(description)
        self.error = ValidationError(name, description)
