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

"""Base authenticator class."""

import logging
from typing import Union

import pam

from zoe_api.auth.file import PlainTextAuthenticator
from zoe_api.auth.ldap import LDAPAuthenticator
from zoe_lib.state import SQLManager, User
from zoe_lib.config import get_conf

log = logging.getLogger(__name__)


class BaseAuthenticator:
    """Base authenticator class."""

    def __init__(self):
        self.state = SQLManager(get_conf())

    def full_auth(self, username: str, password: str) -> Union[None, User]:  # pylint: disable=too-many-return-statements
        """This method verifies the username and the password against one of the external auth sources."""
        user = self.state.user.select(only_one=True, **{"username": username})
        if user is None or not user.enabled:
            return None

        if user.auth_source == "textfile" and PlainTextAuthenticator(get_conf().auth_file).auth(username, password):
            log.info('User {} authenticated via textfile'.format(user.username))
            return user
        elif user.auth_source == "ldap" and LDAPAuthenticator(get_conf(), sasl=False).auth(username, password):
            log.info('User {} authenticated via ldap'.format(user.username))
            return user
        elif user.auth_source == "ldap+sasl" and LDAPAuthenticator(get_conf(), sasl=True).auth(username, password):
            log.info('User {} authenticated via ldap+sasl'.format(user.username))
            return user
        elif user.auth_source == "internal" and user.check_password(password):
            log.info('User {} authenticated via internal db'.format(user.username))
            return user
        elif user.auth_source == "pam" and pam_authenticate(username, password):
            log.info('User {} authenticated via PAM'.format(user.username))
            return user
        else:
            return None


def pam_authenticate(username, password):
    """Use the PAM module to authenticate. Zoe needs access to /etc/shadow."""

    pam_obj = pam.pam()
    return pam_obj.authenticate(username, password)
