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

"""When a service from the application description needs to be instantiated, it is transformed into a ServiceInstance, an internal representation of a generic container. This class is used to gather all the attributes that describe a container and to provide a clear interface with the backend."""

import collections

from zoe_lib.state import Service, Execution
from zoe_lib.config import get_conf
import zoe_master.backends.common

BackendPort = collections.namedtuple('BackendPort', ['number', 'proto'])


class ServiceInstance:
    """The ServiceInstance class, a Service that is going to be instantiated into a container."""
    def __init__(self, execution: Execution, service: Service, env_subst_dict):
        self.name = service.unique_name
        self.hostname = service.dns_name
        self.backend_host = service.backend_host

        if service.resource_reservation.memory.min is None:
            self.memory_limit = None
        else:
            self.memory_limit = service.resource_reservation.memory
            if self.memory_limit.max > get_conf().max_memory_limit * (1024 ** 3):
                self.memory_limit.max = get_conf().max_memory_limit * (1024 ** 3)

        if service.resource_reservation.cores.min is None:
            self.core_limit = None
        else:
            self.core_limit = service.resource_reservation.cores
            if self.core_limit.max > get_conf().max_core_limit:
                self.core_limit = get_conf().max_core_limit

        self.shm_size = service.resource_reservation.shm

        self.labels = {
            'zoe.execution.name': execution.name,
            'zoe.execution.id': str(execution.id),
            'zoe.service.name': service.name,
            'zoe.service.id': str(service.id),
            'zoe.owner': execution.owner.username,
            'zoe.deployment_name': get_conf().deployment_name,
            'zoe.type': 'service_{}'.format('essential' if service.essential else 'elastic'),
            'zoe.zapp_size': execution.size
        }
        if service.is_monitor:
            self.labels['zoe_monitor'] = 'true'
        else:
            self.labels['zoe_monitor'] = 'false'

        self.labels = zoe_master.backends.common.gen_labels(service, execution)
        self.environment = service.environment + zoe_master.backends.common.gen_environment(execution, service, env_subst_dict)
        self.volumes = zoe_master.backends.common.gen_volumes(service, execution)

        self.command = service.command

        self.work_dir = service.work_dir

        self.image_name = service.image_name

        self.load_balancer = service.load_balancer

        self.ports = []
        for port in service.ports:
            self.ports.append(BackendPort(port.internal_number, port.protocol))

        if service.network is not None:
            self.network = service.network
        else:
            self.network = get_conf().overlay_network_name
