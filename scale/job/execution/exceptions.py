"""Defines exceptions that can occur when interacting with job executions"""



class InvalidTaskResults(Exception):
    """Exception indicating that the provided task results JSON was invalid
    """

    pass
