# Copyright (c) 2018, Daniele Venzano
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

"""The User API endpoints."""

import tornado.escape

from zoe_api.rest_api.request_handler import ZoeAPIRequestHandler
from zoe_api.exceptions import ZoeAuthException, ZoeRestAPIException


class UserAPI(ZoeAPIRequestHandler):
    """The User API endpoint. Ops on a single user."""

    def get(self, user_id):
        """HTTP GET method."""
        if self.current_user is None:
            return

        if user_id == self.current_user.id:
            ret = {
                'user': self.current_user.serialize()
            }
        else:
            user = self.api_endpoint.user_by_id(self.current_user, user_id)
            ret = {
                'user': user.serialize()
            }

        self.write(ret)

    def post(self, user_id):
        """HTTP POST method, to edit a user."""
        if self.current_user is None:
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
        except ValueError:
            self.set_status(400, 'Error decoding JSON data')
            return

        try:
            self.api_endpoint.user_update(self.current_user, **data)
        except KeyError:
            self.set_status(400, 'Error decoding JSON data')
            return
        except ZoeAuthException as e:
            self.set_status(401, e.message)
            return

        self.set_status(201)

    def delete(self, user_id: int):
        """HTTP DELETE method."""
        if self.current_user is None:
            return

        try:
            self.api_endpoint.user_delete(self.current_user, user_id)
        except ZoeAuthException as e:
            self.set_status(401, e.message)
            return
        self.set_status(204)


class UserCollectionAPI(ZoeAPIRequestHandler):
    """The UserCollection API. Ops that interact with the User collection."""

    def get(self):
        """HTTP GET method"""
        if self.current_user is None:
            return

        filter_dict = {}

        filters = [
            ('username', str),
            ('email', str),
            ('priority', int),
            ('enabled', bool),
            ('auth_source', str),
            ('role_id', int),
            ('quota_id', int)
        ]
        for filter in filters:
            if filter[0] in self.request.arguments:
                if filter[1] == str:
                    filter_dict[filter[0]] = self.request.arguments[filter[0]][0].decode('utf-8')
                else:
                    filter_dict[filter[0]] = filter[1](self.request.arguments[filter[0]][0])

        try:
            users = self.api_endpoint.user_list(self.current_user, **filter_dict)
        except ZoeAuthException as e:
            self.set_status(401, e.message)
            return

        self.write(dict([(u.id, u.serialize()) for u in users]))

    def post(self):
        """HTTP POST method."""
        if self.current_user is None:
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
        except ValueError:
            self.set_status(400, 'Error decoding JSON data')
            return

        try:
            new_id = self.api_endpoint.user_new(self.current_user, data['username'], data['fs_uid'], data['role'], data['quota'], data['auth_source'])
        except KeyError:
            self.set_status(400, 'Error decoding JSON data')
            return
        except ZoeAuthException as e:
            self.set_status(401, e.message)
            return

        self.set_status(201)
        self.write({'user_id': new_id})
