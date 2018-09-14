"""Defines the class that represents an agent in the scheduler"""



class Agent(object):
    """This class represents an agent available to Scale."""

    def __init__(self, agent_id, hostname):
        """Constructor

        :param agent_id: The agent ID
        :type agent_id: string
        :param hostname: The agent's host name
        :type hostname: string
        """

        self.agent_id = agent_id
        self.hostname = hostname
