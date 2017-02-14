#!/usr/bin/env python3

# Copyright (c) 2016, Quang-Nhat Hoang-Xuan
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

"""Frontend deploy."""

from  docker import Client
import sys

class ZoeFrontendDeploy():
    def __init__(self, dockerUrl, apache2):
        self.src = 'prod.tar'
        self.srcBackup = 'backup.tar'
        self.dst = '/var/www/'
        self.dstBackup = '/var/www/prod'
        self.cli = Client(base_url=dockerUrl)
        self.apache2 = apache2
        return

    def deploy(self):
#    """ Put new frontend folder behind apache2 container """
        try:    
            retcode = 1
            #do backup
            strm, stat = self.cli.get_archive(container=self.apache2, path=self.dstBackup)
            filebackup = open(self.srcBackup, 'wb')
            filebackup.write(strm.read())

            filedata = open(self.src, 'rb').read()
            res = self.cli.put_archive(container=self.apache2, path=self.dst, data=filedata)
            if res is False:
                retcode = 0
        except Exception as ex:
            print(ex)
            retcode = 0
        return retcode

    def fallback(self):
        try:
            retcode = 1
            filebackup = open(self.srcBackup, 'rb').read()
            res = self.cli.put_archive(container=self.apache2, path=self.dst, data=filebackup)
            if res is False:
                retcode = 0
        except Exception as ex:
            print(ex)
            retcode = 0
        return retcode
