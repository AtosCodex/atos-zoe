# Copyright (c) 2017, Quang-Nhat Hoang-Xuan
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

"""Zoe backend implementation for Kubernetes with docker."""

import logging

from zoe_lib.state import Service
from zoe_master.backends.kubernetes.api_client import KubernetesClient
from zoe_master.exceptions import ZoeStartExecutionRetryException, ZoeStartExecutionFatalException, ZoeException, ZoeNotEnoughResourcesException
from zoe_master.backends.service_instance import ServiceInstance
import zoe_master.backends.base
from zoe_master.backends.kubernetes.threads import KubernetesMonitor
from zoe_master.stats import NodeStats, ClusterStats  # pylint: disable=unused-import

log = logging.getLogger(__name__)

# These two module-level variables hold the references to the monitor and checker threads
_monitor = None
_checker = None


class KubernetesBackend(zoe_master.backends.base.BaseBackend):
    """Zoe backend implementation for Kubernetes with docker."""
    def __init__(self, opts):
        super().__init__(opts)
        self.kube = KubernetesClient(opts)

    @classmethod
    def init(cls, state):
        """Initializes Kubernetes backend starting the event monitoring thread."""
        global _monitor, _checker
        _monitor = KubernetesMonitor(state)
#        _checker = KubernetesStateSynchronizer(state)

    @classmethod
    def shutdown(cls):
        """Performs a clean shutdown of the resources used by Kubernetes backend."""
        _monitor.quit()
#        _checker.quit()

    def spawn_service(self, service_instance: ServiceInstance):
        """Spawn a service, translating a Zoe Service into a Docker container."""
        try:
            self.kube.spawn_service(service_instance)
            rc_info = self.kube.spawn_replication_controller(service_instance)
            sr_info = self.kube.inspect_service(service_instance.name)
        except ZoeNotEnoughResourcesException:
            raise ZoeStartExecutionRetryException('Not enough free resources to satisfy reservation request for service {}'.format(service_instance.name))
        except ZoeException as e:
            raise ZoeStartExecutionFatalException(str(e))

        ports = {x['port']: x['nodePort'] for x in sr_info['port_forwarding']}

        return rc_info["backend_id"], rc_info['ip_address'], ports

    def terminate_service(self, service: Service) -> None:
        """Terminate and delete a container."""
        self.kube.terminate(service.dns_name)

    def platform_state(self) -> ClusterStats:
        """Get the platform state."""
        info = self.kube.info()
        for node in info.nodes:  # type: NodeStats
            node.memory_in_use = node.memory_reserved
            node.cores_in_use = node.cores_reserved
        return info

    def preload_image(self, image_name: str) -> None:
        """Make a service image available."""
        raise NotImplementedError

    def update_service(self, service, cores=None, memory=None):
        """Update a service reservation."""
        log.error('Reservation update not implemented in the Kubernetes back-end')

    def node_list(self):
        """Return a list of node names."""
        info = self.kube.info()
        return [node.name for node in info.nodes]

    def list_available_images(self, node_name):
        """List the images available on the specified node."""
        info = self.kube.info()

        for node in info.nodes:
            if node.name == node_name:
                return node.images
        return []
