# Copyright (c) 2016, Daniele Venzano
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

"""RESTful Tornado API definition."""

from typing import List

import tornado.web

from zoe_api.rest_api.execution import ExecutionAPI, ExecutionCollectionAPI, ExecutionDeleteAPI, ExecutionEndpointsAPI
from zoe_api.rest_api.info import InfoAPI
from zoe_api.rest_api.user import UserAPI, UserCollectionAPI
from zoe_api.rest_api.role import RoleAPI, RoleCollectionAPI
from zoe_api.rest_api.quota import QuotaAPI, QuotaCollectionAPI
from zoe_api.rest_api.service import ServiceAPI, ServiceLogsAPI
from zoe_api.rest_api.discovery import DiscoveryAPI
from zoe_api.rest_api.statistics import SchedulerStatsAPI
from zoe_api.rest_api.login import LoginAPI
from zoe_api.rest_api.validation import ZAppValidateAPI

import zoe_lib.config
from zoe_lib.version import ZOE_API_VERSION


def api_init(api_endpoint) -> List[tornado.web.URLSpec]:
    """Initialize the API"""
    route_args = {
        'api_endpoint': api_endpoint
    }
    api_path = zoe_lib.config.get_conf().reverse_proxy_path + '/api/' + ZOE_API_VERSION

    api_routes = [
        tornado.web.url(api_path + r'/info', InfoAPI, route_args),
        tornado.web.url(api_path + r'/login', LoginAPI, route_args),
        tornado.web.url(api_path + r'/zapp_validate', ZAppValidateAPI, route_args),

        tornado.web.url(api_path + r'/user/([0-9]+)', UserAPI, route_args),
        tornado.web.url(api_path + r'/user', UserCollectionAPI, route_args),

        tornado.web.url(api_path + r'/role/([0-9]+)', RoleAPI, route_args),
        tornado.web.url(api_path + r'/role', RoleCollectionAPI, route_args),

        tornado.web.url(api_path + r'/quota/([0-9]+)', QuotaAPI, route_args),
        tornado.web.url(api_path + r'/quota', QuotaCollectionAPI, route_args),

        tornado.web.url(api_path + r'/execution/([0-9]+)', ExecutionAPI, route_args),
        tornado.web.url(api_path + r'/execution/delete/([0-9]+)', ExecutionDeleteAPI, route_args),
        tornado.web.url(api_path + r'/execution/endpoints/([0-9]+)', ExecutionEndpointsAPI, route_args),
        tornado.web.url(api_path + r'/execution', ExecutionCollectionAPI, route_args),

        tornado.web.url(api_path + r'/service/([0-9]+)', ServiceAPI, route_args),
        tornado.web.url(api_path + r'/service/logs/([0-9]+)', ServiceLogsAPI, route_args),

        tornado.web.url(api_path + r'/discovery/by_group/([0-9]+)/([a-z0-9A-Z\-]+)', DiscoveryAPI, route_args),

        tornado.web.url(api_path + r'/statistics/scheduler', SchedulerStatsAPI, route_args)
    ]

    return api_routes
