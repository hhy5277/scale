"""The Scale Mesos scheduler"""
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import logging
import threading
from urlparse import urlparse

from django.utils.timezone import now

from error.models import reset_error_cache
from job.execution.manager import job_exe_mgr
from job.execution.tasks.exe_task import JOB_TASK_ID_PREFIX
from job.models import JobExecution
from job.tasks.manager import task_mgr
from job.tasks.update import TaskStatusUpdate
from mesos_api import utils
from node.resources.node_resources import NodeResources
from node.resources.resource import ScalarResource
from scheduler.cleanup.manager import cleanup_mgr
from scheduler.initialize import initialize_system
from scheduler.manager import scheduler_mgr
from scheduler.messages.restart_scheduler import RestartScheduler
from scheduler.models import Scheduler
from scheduler.node.agent import Agent
from scheduler.node.manager import node_mgr
from scheduler.recon.manager import recon_mgr
from scheduler.resources.manager import resource_mgr
from scheduler.resources.offer import ResourceOffer
from scheduler.sync.job_type_manager import job_type_mgr
from scheduler.sync.workspace_manager import workspace_mgr
from scheduler.task.manager import task_update_mgr
from scheduler.tasks.manager import system_task_mgr
from scheduler.threads.messaging import MessagingThread
from scheduler.threads.recon import ReconciliationThread
from scheduler.threads.schedule import SchedulingThread
from scheduler.threads.scheduler_status import SchedulerStatusThread
from scheduler.threads.sync import SyncThread
from scheduler.threads.task_handling import TaskHandlingThread
from scheduler.threads.task_update import TaskUpdateThread
from util.host import HostAddress


logger = logging.getLogger(__name__)


class ScaleScheduler(MesosScheduler):
    """Mesos scheduler for the Scale framework"""

    # Warning threshold for normal callbacks (those with no external calls, e.g. database queries)
    NORMAL_WARN_THRESHOLD = datetime.timedelta(milliseconds=5)

    def __init__(self):
        """Constructor
        """

        self._driver = None
        self._framework_id = None
        self._master_host_address = None

        self._messaging_thread = None
        self._recon_thread = None
        self._scheduler_status_thread = None
        self._scheduling_thread = None
        self._sync_thread = None
        self._task_handling_thread = None
        self._task_update_thread = None

    def initialize(self):
        """Initializes the scheduler and gets it ready to connect to Mesos. This method should only ever be called once.
        """

        initialize_system()

        # Initial database sync
        logger.info('Performing initial sync with Scale database')
        logger.info('Retrieving errors...')
        reset_error_cache()
        logger.info('Retrieving job execution metrics...')
        job_exe_mgr.init_with_database()
        logger.info('Retrieving job types...')
        job_type_mgr.sync_with_database()
        logger.info('Retrieving workspaces...')
        workspace_mgr.sync_with_database()
        logger.info('Retrieving scheduler settings...')
        scheduler_mgr.sync_with_database()

        # Start up background threads
        logger.info('Starting up background threads')
        self._messaging_thread = MessagingThread()
        restart_msg = RestartScheduler()
        restart_msg.when = now()
        self._messaging_thread.add_initial_messages([restart_msg])
        messaging_thread = threading.Thread(target=self._messaging_thread.run)
        messaging_thread.daemon = True
        messaging_thread.start()

        self._recon_thread = ReconciliationThread()
        recon_thread = threading.Thread(target=self._recon_thread.run)
        recon_thread.daemon = True
        recon_thread.start()

        self._scheduler_status_thread = SchedulerStatusThread()
        scheduler_status_thread = threading.Thread(target=self._scheduler_status_thread.run)
        scheduler_status_thread.daemon = True
        scheduler_status_thread.start()

        self._scheduling_thread = SchedulingThread(self._driver)
        scheduling_thread = threading.Thread(target=self._scheduling_thread.run)
        scheduling_thread.daemon = True
        scheduling_thread.start()

        self._sync_thread = SyncThread(self._driver)
        sync_thread = threading.Thread(target=self._sync_thread.run)
        sync_thread.daemon = True
        sync_thread.start()

        self._task_handling_thread = TaskHandlingThread(self._driver)
        task_handling_thread = threading.Thread(target=self._task_handling_thread.run)
        task_handling_thread.daemon = True
        task_handling_thread.start()

        self._task_update_thread = TaskUpdateThread()
        task_update_thread = threading.Thread(target=self._task_update_thread.run)
        task_update_thread.daemon = True
        task_update_thread.start()

    def registered(self, driver):
        """
        Invoked when the scheduler successfully registers with a Mesos master.
        It is called with the frameworkId, a unique ID generated by the
        master, and the masterInfo which is information about the master
        itself.

        See documentation for :meth:`mesos_api.mesos.Scheduler.registered`.
        """

        self._driver = driver
        self._framework_id = driver.frameworkId
        self._master_host_address = HostAddress(driver.mesos_url)

        logger.info('Scale scheduler registered as framework %s with Mesos master at %s:%i',
                    self._framework_id, self._master_host_address.hostname, self._master_host_address.port)

        ########################################
        # TODO: Remove when API v4 is removed. #
        ########################################
        Scheduler.objects.update_master(self._master_hostname, self._master_port)
        ########################################

        scheduler_mgr.update_from_mesos(self._framework_id, self._master_host_address)

        # Update driver for background threads
        recon_mgr.driver = self._driver
        self._scheduling_thread.driver = self._driver
        self._sync_thread.driver = self._driver
        self._task_handling_thread.driver = self._driver

        self._reconcile_running_jobs()

    def reconnected(self, message):
        """
        Invoked when the scheduler re-registers with a newly elected Mesos
        master.  This is only called when the scheduler has previously been
        registered.  masterInfo contains information about the newly elected
        master.
        """

        self._framework_id = self._driver.frameworkId
        self._master_host_address = HostAddress(self._driver.mesos_url)

        logger.info('Scale scheduler re-registered with Mesos master at %s:%i',
                    self._master_host_address.hostname, self._master_host_address.port)

        ########################################
        # TODO: Remove when API v4 is removed. #
        ########################################
        Scheduler.objects.update_master(self._master_hostname, self._master_port)
        ########################################

        scheduler_mgr.update_from_mesos(mesos_address=self._master_host_address)

        self._reconcile_running_jobs()

    def disconnected(self, message):
        """
        Invoked when the scheduler becomes disconnected from the master, e.g.
        the master fails and another is taking over.
        """

        if self._master_host_address:
            logger.error('Scale scheduler disconnected from the Mesos master at %s:%i: %s',
                         self._master_host_address.hostname, self._master_host_address.port, message)
        else:
            logger.error('Scale scheduler disconnected from the Mesos master: %s', message)

    def offers(self, offers):
        """
        Invoked when resources have been offered to this framework. A single
        offer will only contain resources from a single slave.  Resources
        associated with an offer will not be re-offered to _this_ framework
        until either (a) this framework has rejected those resources (see
        SchedulerDriver.launchTasks) or (b) those resources have been
        rescinded (see Scheduler.offerRescinded).  Note that resources may be
        concurrently offered to more than one framework at a time (depending
        on the allocator being used).  In that case, the first framework to
        launch tasks using those resources will be able to use them while the
        other frameworks will have those resources rescinded (or if a
        framework has already launched tasks with those resources then those
        tasks will fail with a TASK_LOST status and a message saying as much).
        """

        started = now()

        agents = {}
        resource_offers = []
        total_resources = NodeResources()
        for offer in offers:
            offer_id = offer.id.value
            agent_id = offer.slave_id.value
            framework_id = offer.framework_id.value
            hostname = offer.hostname
            resource_list = []
            for resource in offer.resources:
                if resource.type == 0:  # This is the SCALAR type
                    resource_list.append(ScalarResource(resource.name, resource.scalar.value))
            resources = NodeResources(resource_list)
            total_resources.add(resources)
            agents[agent_id] = Agent(agent_id, hostname)
            resource_offers.append(ResourceOffer(offer_id, agent_id, framework_id, resources, started))

        node_mgr.register_agents(agents.values())
        resource_mgr.add_new_offers(resource_offers)

        num_offers = len(resource_offers)
        logger.info('Received %d offer(s) with %s from %d node(s)', num_offers, total_resources, len(agents))
        scheduler_mgr.add_new_offer_count(num_offers)

        duration = now() - started
        msg = 'Scheduler resourceOffers() took %.3f seconds'
        if duration > ScaleScheduler.NORMAL_WARN_THRESHOLD:
            logger.warning(msg, duration.total_seconds())
        else:
            logger.debug(msg, duration.total_seconds())

    def rescind(self, offerId):
        """
        Invoked when an offer is no longer valid (e.g., the slave was lost or
        another framework used resources in the offer.) If for whatever reason
        an offer is never rescinded (e.g., dropped message, failing over
        framework, etc.), a framwork that attempts to launch tasks using an
        invalid offer will receive TASK_LOST status updats for those tasks.
        """

        started = now()

        offer_id = offerId.value
        resource_mgr.rescind_offers([offer_id])

        duration = now() - started
        msg = 'Scheduler offerRescinded() took %.3f seconds'
        if duration > ScaleScheduler.NORMAL_WARN_THRESHOLD:
            logger.warning(msg, duration.total_seconds())
        else:
            logger.debug(msg, duration.total_seconds())

    def update(self, status):
        """
        Invoked when the status of a task has changed (e.g., a slave is lost
        and so the task is lost, a task finishes and an executor sends a
        status update saying so, etc.) Note that returning from this callback
        acknowledges receipt of this status update.  If for whatever reason
        the scheduler aborts during this callback (or the process exits)
        another status update will be delivered.  Note, however, that this is
        currently not true if the slave sending the status update is lost or
        fails during that time.
        """

        started = now()

        model = utils.create_task_update_model(status)
        mesos_status = model.status
        task_update = TaskStatusUpdate(model, utils.get_status_agent_id(status), utils.get_status_data(status))
        task_id = task_update.task_id
        was_task_finished = task_update.status in TaskStatusUpdate.TERMINAL_STATUSES
        was_job_finished = False

        if mesos_status == 'TASK_ERROR':
            logger.error('Status update for task %s: %s', task_id, mesos_status)
        if mesos_status == 'TASK_LOST':
            logger.warning('Status update for task %s: %s', task_id, mesos_status)
        else:
            logger.info('Status update for task %s: %s', task_id, mesos_status)

        # Since we have a status update for this task, remove it from reconciliation set
        recon_mgr.remove_task_id(task_id)

        # Hand off task update to be saved in the database
        if task_id.startswith(JOB_TASK_ID_PREFIX):
            # Grab job execution ID from manager
            cluster_id = JobExecution.parse_cluster_id(task_id)
            job_exe = job_exe_mgr.get_running_job_exe(cluster_id)
            if job_exe:
                model.job_exe_id = job_exe.id
        task_update_mgr.add_task_update(model)

        # Update task with latest status
        # This should happen before the job execution or node manager are updated, since they will assume that the task
        # has already been updated
        task_mgr.handle_task_update(task_update)

        if task_id.startswith(JOB_TASK_ID_PREFIX):
            # Job task, so update the job execution
            try:
                job_exe = job_exe_mgr.handle_task_update(task_update)
                if job_exe and job_exe.is_finished():
                    was_job_finished = True
                    cleanup_mgr.add_job_execution(job_exe)
            except Exception:
                cluster_id = JobExecution.parse_cluster_id(task_id)
                logger.exception('Error handling status update for job execution: %s', cluster_id)
                # Error handling status update, add task so it can be reconciled
                task = task_mgr.get_task(task_id)
                if task:
                    recon_mgr.add_tasks([task])
        else:
            # Not a job task, so must be either a node or system task
            node_mgr.handle_task_update(task_update)
            system_task_mgr.handle_task_update(task_update)

        scheduler_mgr.add_task_update_counts(was_task_finished, was_job_finished)

        duration = now() - started
        msg = 'Scheduler statusUpdate() took %.3f seconds'
        if duration > ScaleScheduler.NORMAL_WARN_THRESHOLD:
            logger.warning(msg, duration.total_seconds())
        else:
            logger.debug(msg, duration.total_seconds())

    def error(self, message):
        """
        Invoked when there is an unrecoverable error in the scheduler or
        scheduler driver.  The driver will be aborted BEFORE invoking this
        callback.
        """

        logger.error('Unrecoverable error: %s', message)

    def shutdown(self):
        """Performs any clean up required by this scheduler implementation.

        Currently this method just notifies any background threads to break out of their work loops.
        """

        logger.info('Scheduler shutdown invoked, stopping background threads')
        self._messaging_thread.shutdown()
        self._recon_thread.shutdown()
        self._scheduler_status_thread.shutdown()
        # TODO: Ensure driver is cleaned up
        self._scheduling_thread.shutdown()
        self._sync_thread.shutdown()
        self._task_handling_thread.shutdown()
        self._task_update_thread.shutdown()

    def _reconcile_running_jobs(self):
        """Reconciles all currently running job executions with Mesos"""

        # List of tasks to reconcile
        tasks_to_reconcile = []

        # Find current tasks for running executions
        for running_job_exe in job_exe_mgr.get_running_job_exes():
            task = running_job_exe.current_task
            if task:
                tasks_to_reconcile.append(task)

        # Send tasks to reconciliation thread
        recon_mgr.add_tasks(tasks_to_reconcile)
