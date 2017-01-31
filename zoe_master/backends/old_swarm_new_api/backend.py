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

"""Zoe backend implementation for old-style stand-alone Docker Swarm."""

import logging

from zoe_lib.exceptions import ZoeLibException, ZoeNotEnoughResourcesException
from zoe_lib.state import Service
from zoe_master.backends.old_swarm_new_api.api_client import SwarmClient
from zoe_master.exceptions import ZoeStartExecutionRetryException, ZoeStartExecutionFatalException, ZoeException
import zoe_master.backends.base
from zoe_master.backends.service_instance import ServiceInstance
from zoe_master.backends.old_swarm_new_api.threads import SwarmMonitor, SwarmStateSynchronizer
from zoe_master.stats import NodeStats, ClusterStats  # pylint: disable=unused-import

log = logging.getLogger(__name__)

# These two module-level variables hold the references to the monitor and checker threads
_monitor = None
_checker = None


class OldSwarmNewAPIBackend(zoe_master.backends.base.BaseBackend):
    """Zoe backend implementation for old-style stand-alone Docker Swarm."""
    def __init__(self, opts):
        super().__init__(opts)
        self.swarm = SwarmClient(opts)

    @classmethod
    def init(cls, state):
        """Initializes Swarm backend starting the event monitoring thread."""
        global _monitor, _checker
        _monitor = SwarmMonitor(state)
        _checker = SwarmStateSynchronizer(state)

    @classmethod
    def shutdown(cls):
        """Performs a clean shutdown of the resources used by Swarm backend."""
        _monitor.quit()
        _checker.quit()

    def spawn_service(self, service_instance: ServiceInstance):
        """Spawn a service, translating a Zoe Service into a Docker container."""
        try:
            cont_info = self.swarm.spawn_container(service_instance)
        except ZoeNotEnoughResourcesException:
            raise ZoeStartExecutionRetryException('Not enough free resources to satisfy reservation request for service {}'.format(service_instance.name))
        except (ZoeException, ZoeLibException) as e:
            raise ZoeStartExecutionFatalException(str(e))

        return cont_info["id"]

    def terminate_service(self, service: Service) -> None:
        """Terminate and delete a container."""
        self.swarm.terminate_container(service.backend_id, delete=True)

    def platform_state(self) -> ClusterStats:
        """Get the platform state."""
        info = self.swarm.info()
        for node in info.nodes:  # type: NodeStats
            node.memory_free = node.memory_total - node.memory_reserved
            node.cores_free = node.cores_total - node.cores_reserved
        return info
