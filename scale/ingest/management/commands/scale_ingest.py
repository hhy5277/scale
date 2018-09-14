"""Defines the command line method for running an ingest task"""


import logging
import signal
import sys
from optparse import make_option

from django.core.management.base import BaseCommand

import ingest.ingest_job as ingest_job

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command that executes the ingest process for a given ingest model
    """

    help = 'Perform the ingest process on an ingest model'
    
    def add_arguments(self, parser):
        parser.add_argument('-i', '--ingest-id', action='store', type=int,
                            help='ID of the ingest model')

    def handle(self, *args, **options):
        """See :meth:`django.core.management.base.BaseCommand.handle`.

        This method starts the ingest process.
        """

        # Register a listener to handle clean shutdowns
        signal.signal(signal.SIGTERM, self._onsigterm)

        ingest_id = options.get('ingest_id')

        logger.info('Command starting: scale_ingest')
        logger.info('Ingest ID: %i', ingest_id)
        try:
            ingest_job.perform_ingest(ingest_id)
        except:
            logger.exception('Ingest caught unexpected error, exit code 1 returning')
            sys.exit(1)
        logger.info('Command completed: scale_ingest')

    def _onsigterm(self, signum, _frame):
        """See signal callback registration: :py:func:`signal.signal`.

        This callback performs a clean shutdown when a TERM signal is received.
        """

        logger.info('Ingest terminating due to receiving sigterm')
        sys.exit(1)
