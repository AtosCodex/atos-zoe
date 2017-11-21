# Copyright (c) 2017, Daniele Venzano
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The Elastic scheduler is the implementation of the scheduling algorithm presented in this paper:
https://arxiv.org/abs/1611.09528
"""

from collections import namedtuple
import logging
import threading
import time

from zoe_lib.state import Execution, SQLManager, Service  # pylint: disable=unused-import
from zoe_master.exceptions import ZoeException

from zoe_master.backends.interface import terminate_execution, get_platform_state, start_elastic, start_essential, update_service_resource_limits
from zoe_master.scheduler.simulated_platform import SimulatedPlatform
from zoe_master.exceptions import UnsupportedSchedulerPolicyError
from zoe_master.stats import NodeStats  # pylint: disable=unused-import

log = logging.getLogger(__name__)

ExecutionProgress = namedtuple('ExecutionProgress', ['last_time_scheduled', 'progress_sequence'])
SELF_TRIGGER_TIMEOUT = 60  # the scheduler will trigger itself periodically in case platform resources have changed outside its control


class ZoeElasticScheduler:
    """The Scheduler class for size-based scheduling. Policy can be "FIFO" or "SIZE"."""
    def __init__(self, state: SQLManager, policy):
        if policy != 'FIFO' and policy != 'SIZE':
            raise UnsupportedSchedulerPolicyError
        self.trigger_semaphore = threading.Semaphore(0)
        self.policy = policy
        self.queue = []
        self.queue_running = []
        self.additional_exec_state = {}
        self.async_threads = []
        self.loop_quit = False
        self.loop_th = threading.Thread(target=self._thread_wrapper, name='scheduler')
        self.core_limit_recalc_trigger = threading.Event()
        self.core_limit_th = threading.Thread(target=self._adjust_core_limits, name='adjust_core_limits')
        self.state = state
        for execution in self.state.executions.select(status='running'):
            if execution.all_services_running:
                self.queue_running.append(execution)
            else:
                self.queue.append(execution)
                self.additional_exec_state[execution.id] = ExecutionProgress(0, [])
        self.loop_th.start()
        self.core_limit_th.start()

    def trigger(self):
        """Trigger a scheduler run."""
        self.trigger_semaphore.release()

    def incoming(self, execution: Execution):
        """
        This method adds the execution to the end of the queue and triggers the scheduler.
        :param execution: The execution
        :return:
        """
        exec_data = ExecutionProgress(0, [])
        self.additional_exec_state[execution.id] = exec_data
        self.queue.append(execution)
        self.trigger()

    def terminate(self, execution: Execution) -> None:
        """
        Inform the master that an execution has been terminated. This can be done asynchronously.
        :param execution: the terminated execution
        :return: None
        """
        def async_termination(e):
            """Actual termination runs in a thread."""
            with e.termination_lock:
                try:
                    terminate_execution(e)
                except ZoeException as ex:
                    log.error('Error in termination thread: {}'.format(ex))
                    return
                self.trigger()
            log.debug('Execution {} terminated successfully'.format(e.id))

        try:
            self.queue.remove(execution)
        except ValueError:
            try:
                self.queue_running.remove(execution)
            except ValueError:
                log.error('Cannot terminate execution {}, it is not in any queue'.format(execution.id))
                return

        try:
            del self.additional_exec_state[execution.id]
        except KeyError:
            pass
        self.core_limit_recalc_trigger.set()

        th = threading.Thread(target=async_termination, name='termination_{}'.format(execution.id), args=(execution,))
        th.start()
        self.async_threads.append(th)

    def _cleanup_async_threads(self):
        counter = len(self.async_threads)
        while counter > 0:
            if len(self.async_threads) == 0:
                break
            th = self.async_threads.pop(0)
            th.join(0.1)
            if th.isAlive():  # join failed
                # log.debug('Thread {} join failed'.format(th.name))
                self.async_threads.append(th)
            counter -= 1

    def _refresh_execution_sizes(self):
        for execution in self.queue:  # type: Execution
            exec_data = self.additional_exec_state[execution.id]
            if exec_data.last_time_scheduled == 0:
                progress = 0
            else:
                last_progress = (time.time() - exec_data.last_time_scheduled) / ((execution.services_count / execution.running_services_count) * execution.size)
                exec_data.progress_sequence.append(last_progress)
                progress = sum(exec_data.progress_sequence)
            remaining_execution_time = (1 - progress) * execution.size
            execution.size = remaining_execution_time * execution.services_count

    def _pop_all_with_same_size(self):
        out_list = []
        while len(self.queue) > 0:
            job = self.queue.pop(0)  # type: Execution
            ret = job.termination_lock.acquire(blocking=False)
            if ret and job.status != Execution.TERMINATED_STATUS:
                out_list.append(job)
            else:
                log.debug('While popping, throwing away execution {} that has the termination lock held'.format(job.id))

        return out_list

    def _thread_wrapper(self):
        while True:
            try:
                self.loop_start_th()
            except BaseException:  # pylint: disable=broad-except
                log.exception('Unmanaged exception in scheduler loop')
            else:
                log.debug('Scheduler thread terminated')
                break

    def loop_start_th(self):
        """The Scheduler thread loop."""
        auto_trigger = SELF_TRIGGER_TIMEOUT
        while True:
            ret = self.trigger_semaphore.acquire(timeout=1)
            if not ret:  # Semaphore timeout, do some thread cleanup
                self._cleanup_async_threads()
                auto_trigger -= 1
                if auto_trigger == 0:
                    auto_trigger = SELF_TRIGGER_TIMEOUT
                    self.trigger()
                continue
            if self.loop_quit:
                break

            if len(self.queue) == 0:
                log.debug("Scheduler loop has been triggered, but the queue is empty")
                self.core_limit_recalc_trigger.set()
                continue
            log.debug("Scheduler loop has been triggered")

            while True:  # Inner loop will run until no new executions can be started or the queue is empty
                self._refresh_execution_sizes()

                if self.policy == "SIZE":
                    self.queue.sort(key=lambda execution: execution.size)

                log.debug('--> Queue dump after sorting')
                for j in self.queue:
                    log.debug(str(j))
                log.debug('--> End dump')

                jobs_to_attempt_scheduling = self._pop_all_with_same_size()
                log.debug('Scheduler inner loop, jobs to attempt scheduling:')
                for job in jobs_to_attempt_scheduling:
                    log.debug("-> {}".format(job))

                try:
                    platform_state = get_platform_state()
                except ZoeException:
                    log.error('Cannot retrieve platform state, cannot schedule')
                    for job in jobs_to_attempt_scheduling:
                        job.termination_lock.release()
                    self.queue = jobs_to_attempt_scheduling + self.queue
                    break

                cluster_status_snapshot = SimulatedPlatform(platform_state)
                log.debug(str(cluster_status_snapshot))

                jobs_to_launch = []
                free_resources = cluster_status_snapshot.aggregated_free_memory()

                # Try to find a placement solution using a snapshot of the platform status
                for job in jobs_to_attempt_scheduling:  # type: Execution
                    jobs_to_launch_copy = jobs_to_launch.copy()

                    # remove all elastic services from the previous simulation loop
                    for job_aux in jobs_to_launch:  # type: Execution
                        cluster_status_snapshot.deallocate_elastic(job_aux)

                    job_can_start = False
                    if not job.is_running:
                        job_can_start = cluster_status_snapshot.allocate_essential(job)

                    if job_can_start or job.is_running:
                        jobs_to_launch.append(job)

                    # Try to put back the elastic services
                    for job_aux in jobs_to_launch:
                        cluster_status_snapshot.allocate_elastic(job_aux)

                    current_free_resources = cluster_status_snapshot.aggregated_free_memory()
                    if current_free_resources >= free_resources:
                        jobs_to_launch = jobs_to_launch_copy
                        break
                    free_resources = current_free_resources

                placements = cluster_status_snapshot.get_service_allocation()
                log.debug('Allocation after simulation: {}'.format(placements))

                # We port the results of the simulation into the real cluster
                for job in jobs_to_launch:  # type: Execution
                    if not job.essential_services_running:
                        ret = start_essential(job, placements)
                        if ret == "fatal":
                            jobs_to_attempt_scheduling.remove(job)
                            continue  # trow away the execution
                        elif ret == "requeue":
                            self.queue.insert(0, job)
                            continue
                        elif ret == "ok":
                            job.set_running()

                        assert ret == "ok"

                    start_elastic(job, placements)

                    if job.all_services_active:
                        log.debug('execution {}: all services are active'.format(job.id))
                        job.termination_lock.release()
                        jobs_to_attempt_scheduling.remove(job)
                        self.queue_running.append(job)

                self.core_limit_recalc_trigger.set()

                for job in jobs_to_attempt_scheduling:
                    job.termination_lock.release()
                    # self.queue.insert(0, job)

                self.queue = jobs_to_attempt_scheduling + self.queue

                if len(self.queue) == 0:
                    log.debug('empty queue, exiting inner loop')
                    break
                if len(jobs_to_launch) == 0:
                    log.debug('No executions could be started, exiting inner loop')
                    break

    def quit(self):
        """Stop the scheduler thread."""
        self.loop_quit = True
        self.trigger()
        self.core_limit_recalc_trigger.set()
        self.loop_th.join()
        self.core_limit_th.join()

    def stats(self):
        """Scheduler statistics."""
        if self.policy == "SIZE":
            queue = sorted(self.queue, key=lambda execution: execution.size)
        else:
            queue = self.queue

        return {
            'queue_length': len(self.queue),
            'running_length': len(self.queue_running),
            'termination_threads_count': len(self.async_threads),
            'queue': [s.id for s in queue],
            'running_queue': [s.id for s in self.queue_running]
        }

    def _adjust_core_limits(self):
        while not self.loop_quit:
            self.core_limit_recalc_trigger.wait()
            if self.loop_quit:
                break
            log.debug('Updating core limits')
            time_start = time.time()
            stats = get_platform_state()
            for node in stats.nodes:  # type: NodeStats
                new_core_allocations = {}
                node_services = self.state.services.select(backend_host=node.name, backend_status=Service.BACKEND_START_STATUS)
                if len(node_services) == 0:
                    continue

                for service in node_services:
                    new_core_allocations[service.id] = service.resource_reservation.cores.min

                if node.cores_reserved < node.cores_total:
                    cores_free = node.cores_total - node.cores_reserved
                    cores_to_add = cores_free / len(node_services)
                else:
                    cores_to_add = 0

                for service in node_services:
                    update_service_resource_limits(service, cores=new_core_allocations[service.id] + cores_to_add)

            log.debug('Update core limits took {:.2f}s'.format(time.time() - time_start))
            self.core_limit_recalc_trigger.clear()
