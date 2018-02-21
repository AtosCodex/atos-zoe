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

"""Exceptions used by the API component."""


class ZoeException(Exception):
    """
    A generic exception.
    """
    def __init__(self, message='Something happened'):
        super().__init__()
        self.message = message
        self.status_code = 500

    def __str__(self):
        return '{}: {}'.format(self.status_code, self.message)


class ZoeAuthException(ZoeException):
    """An authentication error."""
    def __init__(self, message=None):
        super().__init__()
        if message is None:
            self.message = 'Unauthorized'
        else:
            self.message = message
        self.status_code = 401


class ZoeNotFoundException(ZoeException):
    """The user is looking for an object that does not exist."""
    def __init__(self, message=None):
        super().__init__()
        if message is None:
            self.message = 'Not found'
        else:
            self.message = message
        self.status_code = 404


class ZoeRestAPIException(ZoeException):
    """
    An exception generated by the REST API.
    """
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
