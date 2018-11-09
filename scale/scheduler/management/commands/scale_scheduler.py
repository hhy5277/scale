from __future__ import unicode_literals

import logging
import os
import signal
import socket
import sys

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand
from mesos.interface import mesos_pb2
try:
    from mesos.native import MesosSchedulerDriver
except ImportError:
    # ensure there are not undefined errors when generating docs on a system without mesos bindings
    class MesosSchedulerDriver(object):
        def __init__(self, *args, **kargs):
            pass

from scheduler.manager import scheduler_mgr
from scheduler.scale_scheduler import ScaleScheduler

logger = logging.getLogger(__name__)

#TODO: make these command options
MESOS_CHECKPOINT = False
MESOS_AUTHENTICATE = False
DEFAULT_PRINCIPLE = None
DEFAULT_SECRET = None


GLOBAL_SHUTDOWN = None


class Command(BaseCommand):
    """Command that launches the Scale scheduler
    """

    help = 'Launches the Scale scheduler'

    def add_arguments(self, parser):
        parser.add_argument('-m', '--master', action='store',
                            default=settings.MESOS_MASTER,
                            help='The master to connect to')

    def handle(self, *args, **options):
        """See :meth:`django.core.management.base.BaseCommand.handle`.

        This method starts the scheduler.
        """

        # Register a listener to handle clean shutdowns
        signal.signal(signal.SIGTERM, self._onsigterm)

        # Set up global shutdown
        global GLOBAL_SHUTDOWN
        GLOBAL_SHUTDOWN = self._shutdown

        # TODO: clean this up
        mesos_master = options.get('master')

        logger.info('Scale Scheduler %s', settings.VERSION)

        try:
            scheduler_zk = settings.SCHEDULER_ZK
        except:
            scheduler_zk = None

        if scheduler_zk is not None:
            from scheduler import cluster_utils
            my_id = socket.gethostname()
            cluster_utils.wait_for_leader(scheduler_zk, my_id, self.run_scheduler, mesos_master)
        else:
            # leader election is disabled
            self.run_scheduler(mesos_master)

    def run_scheduler(self, mesos_master):
        logger.info("Scale rising...")
        self.scheduler = ScaleScheduler()
        self.scheduler.initialize()
        scheduler_mgr.hostname = socket.getfqdn()

        framework = mesos_pb2.FrameworkInfo()
        framework.user = ''  # Have Mesos fill in the current user.
        framework.name = os.getenv('DCOS_PACKAGE_FRAMEWORK_NAME', 'Scale')
        capability = framework.capabilities.add()
        capability.type = mesos_pb2.FrameworkInfo.Capability.GPU_RESOURCES
        webserver_address = os.getenv('SCALE_WEBSERVER_ADDRESS')

        principal = os.getenv('PRINCIPAL')
        secret = os.getenv('SECRET')

        if webserver_address:
            framework.webui_url = webserver_address

        logger.info('Connecting to Mesos master at %s', mesos_master)
    
        # TODO(vinod): Make checkpointing the default when it is default on the slave.
        if MESOS_CHECKPOINT:
            logger.info('Enabling checkpoint for the framework')
            framework.checkpoint = True

        if principal and secret:
            logger.info('Enabling authentication for the framework')

            credential = mesos_pb2.Credential()
            credential.principal = principal
            credential.secret = secret

            self.driver = MesosSchedulerDriver(self.scheduler, framework, mesos_master, credential)
        else:
            logger.info('Framework authentication skipped due to missing PRINCIPAL and SECRET env variables')

            self.driver = MesosSchedulerDriver(self.scheduler, framework, mesos_master)

        try:
            status = 0 if self.driver.run() == mesos_pb2.DRIVER_STOPPED else 1
        except:
            status = 1
            logger.exception('Mesos Scheduler Driver returned an exception')

        #Perform a shut down and return any non-zero status
        shutdown_status = self._shutdown()
        status = status or shutdown_status

        logger.info('Exiting...')
        sys.exit(status)

    def _onsigterm(self, signum, _frame):
        """See signal callback registration: :py:func:`signal.signal`.

        This callback performs a clean shutdown when a TERM signal is received.
        """
        logger.info('Scheduler command terminated due to signal: %i', signum)
        self._shutdown()
        sys.exit(1)

    def _shutdown(self):
        """Performs any clean up required by this command.

        :returns: The exit status code based on whether the shutdown operation was clean with no exceptions.
        :rtype: int
        """
        status = 0

        try:
            if self.scheduler:
                self.scheduler.shutdown()
        except:
            logger.exception('Failed to properly shutdown Scale scheduler.')
            status = 1

        try:
            if self.driver:
                self.driver.stop()
        except:
            logger.exception('Failed to properly stop Mesos driver.')
            status = 1
        return status
