"""Defines exceptions that can occur when interacting with a job interface"""


from error.exceptions import ScaleError


class InvalidInterfaceDefinition(Exception):
    """Exception indicating that the provided definition of a job interface was invalid
    """
    pass


class InvalidEnvironment(Exception):
    """Exception indicating that the provided definition of a job interface was invalid
    """
    pass
